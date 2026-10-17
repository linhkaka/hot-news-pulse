"""YouTube Data API v3: watch channels and alert when a video crosses the threshold.

Only needs an API key: view counts of public videos are public data.
Quota cost per channel per scan is about 2 units (playlistItems + videos);
the free daily quota is 10,000 units.
"""

import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger("reels_tracker.youtube")

API_BASE = "https://www.googleapis.com/youtube/v3"
DAILY_QUOTA = 10_000
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}
KEY_REASONS = {"keyInvalid", "keyExpired", "accessNotConfigured", "forbidden", "ipRefererBlocked"}
QUOTA_COOLDOWN_SECONDS = 60 * 60

CHANNEL_ID_RE = re.compile(r"(UC[\w-]{22})")
HANDLE_RE = re.compile(r"@([\w.\-·]+)")


class YouTubeError(Exception):
    pass


class QuotaError(YouTubeError):
    pass


class ApiKeyError(YouTubeError):
    pass


def parse_yt_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def video_link(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def parse_channel_input(text):
    """('id', 'UC...') or ('handle', '@name') from an ID, @handle or channel URL."""
    text = text.strip()
    match = CHANNEL_ID_RE.search(text)
    if match:
        return "id", match.group(1)
    match = HANDLE_RE.search(text)
    if match:
        return "handle", "@" + match.group(1)
    if re.fullmatch(r"[\w.\-]+", text):
        return "handle", "@" + text
    return None, None


class YouTubeClient:
    def __init__(self, api_key, session=None, retries=3, backoff_seconds=2.0, sleep=time.sleep):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep

    def get(self, endpoint, **params):
        params["key"] = self.api_key
        for attempt in range(self.retries):
            try:
                resp = self.session.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
                data = resp.json()
            except (requests.RequestException, ValueError) as e:
                if attempt == self.retries - 1:
                    raise YouTubeError(f"network error: {e}") from e
                self.sleep(self.backoff_seconds * 2**attempt)
                continue
            if "error" in data:
                err = data["error"]
                reasons = {e.get("reason") for e in err.get("errors", [])}
                message = err.get("message", "unknown error")
                if reasons & QUOTA_REASONS:
                    raise QuotaError(message)
                if reasons & KEY_REASONS or "API key" in message:
                    raise ApiKeyError(message)
                raise YouTubeError(message)
            return data

    def resolve_channel(self, text):
        """Return {'id', 'title', 'uploads'} for a channel ID, @handle or URL, or None."""
        kind, value = parse_channel_input(text)
        if not kind:
            return None
        params = {"id": value} if kind == "id" else {"forHandle": value}
        data = self.get("channels", part="snippet,contentDetails", **params)
        items = data.get("items") or []
        if not items:
            return None
        item = items[0]
        return {
            "id": item["id"],
            "title": item["snippet"]["title"],
            "uploads": item["contentDetails"]["relatedPlaylists"]["uploads"],
        }

    def recent_video_ids(self, uploads_playlist, since, max_items=200):
        """IDs of videos in the uploads playlist published after `since` (newest first)."""
        ids, page_token = [], None
        while len(ids) < max_items:
            params = {"part": "contentDetails", "playlistId": uploads_playlist, "maxResults": 50}
            if page_token:
                params["pageToken"] = page_token
            data = self.get("playlistItems", **params)
            for item in data.get("items", []):
                details = item.get("contentDetails", {})
                published = parse_yt_time(details.get("videoPublishedAt"))
                if published and published < since:
                    return ids
                ids.append(details["videoId"])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return ids

    def videos(self, video_ids):
        """Stats for up to any number of videos (50 per request)."""
        result = []
        for start in range(0, len(video_ids), 50):
            batch = video_ids[start:start + 50]
            data = self.get("videos", part="snippet,statistics", id=",".join(batch), maxResults=50)
            for item in data.get("items", []):
                snippet, stats = item.get("snippet", {}), item.get("statistics", {})
                if snippet.get("liveBroadcastContent") == "upcoming" or "viewCount" not in stats:
                    continue
                result.append({
                    "id": item["id"],
                    "title": snippet.get("title", ""),
                    "published": parse_yt_time(snippet.get("publishedAt")),
                    "views": int(stats["viewCount"]),
                })
        return result


def format_video_message(channel_title, video, threshold, now, format_age):
    lines = [
        f"🔥 Video YouTube vượt {threshold:,} view",
        f"Kênh: {channel_title}",
        f"Tiêu đề: {video['title']}",
        f"Views: {video['views']:,}",
    ]
    if video.get("published"):
        lines.append(f"Đăng cách đây: {format_age(video['published'], now)}")
    lines.append(video_link(video["id"]))
    return "\n".join(lines)


class YouTubeScanner:
    def __init__(self, cfg, client, store, telegram, threshold_fn, format_age, clock=time.time):
        self.cfg = cfg
        self.client = client
        self.store = store
        self.telegram = telegram
        self.threshold_fn = threshold_fn
        self.format_age = format_age
        self.clock = clock
        self.next_due = 0
        self.cooldown_until = 0
        self.last_scan_at = None
        self.last_scan_result = "chưa quét"
        self._key_alert_sent = False

    def ready(self, forced=False):
        now = self.clock()
        return now >= self.cooldown_until and (forced or now >= self.next_due)

    def seconds_until_due(self):
        return max(self.next_due, self.cooldown_until) - self.clock()

    def estimated_daily_quota(self):
        scans_per_day = 86400 / self.cfg["youtube_poll_interval_seconds"]
        return math.ceil(scans_per_day * len(self.store.active_channels()) * 2)

    def seed_channels(self, inputs):
        """Add channels from config once; channels removed via /removeyt stay removed."""
        for text in inputs:
            key = f"yt_seeded:{text}"
            if self.store.get_setting(key):
                continue
            try:
                channel = self.client.resolve_channel(text)
            except YouTubeError as e:
                log.error("Could not resolve YouTube channel %s: %s", text, e)
                continue
            if not channel:
                log.error("YouTube channel not found: %s", text)
                continue
            self.store.add_channel(channel["id"], channel["title"], channel["uploads"])
            self.store.set_setting(key, channel["id"])

    def add_channel(self, text):
        try:
            channel = self.client.resolve_channel(text)
        except YouTubeError as e:
            return f"❌ Lỗi YouTube API: {e}"
        if not channel:
            return f"❌ Không tìm thấy kênh '{text}'. Dùng @handle, ID kênh (UC...) hoặc link kênh."
        self.store.add_channel(channel["id"], channel["title"], channel["uploads"])
        self.next_due = 0
        msg = f"✅ Đã thêm kênh {channel['title']} ({channel['id']})"
        quota = self.estimated_daily_quota()
        if quota > DAILY_QUOTA * 0.9:
            msg += (
                f"\n⚠️ Ước tính dùng ~{quota:,}/{DAILY_QUOTA:,} quota/ngày — "
                "hãy tăng YOUTUBE_POLL_INTERVAL_SECONDS."
            )
        return msg

    def _send_key_alert(self, error):
        if self._key_alert_sent:
            return
        self._key_alert_sent = True
        text = f"⚠️ YouTube API key không dùng được ({error}). Kiểm tra lại YOUTUBE_API_KEY."
        log.error(text)
        try:
            self.telegram.send(text)
        except Exception as e:  # alerting must never crash the scan loop
            log.warning("Could not send YouTube key alert: %s", e)

    def scan_once(self):
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=self.cfg["max_reel_age_days"])
        threshold = self.threshold_fn()
        channels = self.store.active_channels()
        sent = checked = 0
        self.next_due = self.clock() + self.cfg["youtube_poll_interval_seconds"]
        try:
            for channel_id, title, uploads in channels:
                try:
                    ids = self.client.recent_video_ids(uploads, since)
                except (QuotaError, ApiKeyError):
                    raise
                except YouTubeError as e:
                    log.error("Could not list videos for %s: %s", title, e)
                    continue
                pending = [vid for vid in ids if not self.store.yt_was_notified(vid)]
                videos = self.client.videos(pending) if pending else []
                log.info("YouTube %s: %d recent videos", title, len(ids))
                for video in videos:
                    checked += 1
                    link = video_link(video["id"])
                    self.store.save_yt_video(video["id"], channel_id, video["title"], link, video["views"])
                    if video["views"] < threshold:
                        continue
                    try:
                        self.telegram.send(
                            format_video_message(title, video, threshold, now, self.format_age)
                        )
                    except Exception as e:  # retry on the next scan
                        log.error("Telegram send failed for video %s: %s", video["id"], e)
                        continue
                    self.store.mark_yt_notified(video["id"])
                    sent += 1
                    log.info("Notified YouTube video %s (%d views)", video["id"], video["views"])
        except QuotaError as e:
            self.cooldown_until = self.clock() + QUOTA_COOLDOWN_SECONDS
            self.last_scan_result = "hết quota YouTube, tạm nghỉ 1 giờ"
            log.warning("YouTube quota exceeded (%s); pausing", e)
            return sent
        except ApiKeyError as e:
            self.last_scan_result = "lỗi API key YouTube"
            self._send_key_alert(e)
            return sent
        except YouTubeError as e:
            self.last_scan_result = f"lỗi: {e}"
            log.error("YouTube scan failed: %s", e)
            return sent

        self._key_alert_sent = False
        self.last_scan_at = self.clock()
        self.last_scan_result = f"{len(channels)} kênh, {checked} video, gửi {sent} thông báo"
        log.info("YouTube scan done: %s", self.last_scan_result)
        return sent
