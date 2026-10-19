"""YouTube: watch channels and alert when a video crosses the threshold.

Two official sources are used:
- The public RSS feed of each channel (free, no key): lists the 15 newest
  videos with their view counts. Used to discover new videos every scan.
- The YouTube Data API v3 (optional API key): fresher view counts, looked up
  for up to 50 videos per request, so one quota unit covers many channels.
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

from net import ThreadSessions

log = logging.getLogger("reels_tracker.youtube")

API_BASE = "https://www.googleapis.com/youtube/v3"
RSS_URL = "https://www.youtube.com/feeds/videos.xml"
RSS_MAX_ENTRIES = 15
DAILY_QUOTA = 10_000
# YouTube resets the quota at midnight Pacific time; a fixed offset is close enough.
QUOTA_TZ = timezone(timedelta(hours=-8))
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}
KEY_REASONS = {"keyInvalid", "keyExpired", "accessNotConfigured", "forbidden", "ipRefererBlocked"}
QUOTA_COOLDOWN_SECONDS = 60 * 60

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
CHANNEL_ID_RE = re.compile(r"(UC[\w-]{22})")
HANDLE_RE = re.compile(r"@([\w.\-·]+)")

FIND_CHANNEL_ID_HELP = (
    "Cách lấy ID kênh: mở kênh YouTube → bấm vào phần mô tả kênh (… thêm) → "
    "Chia sẻ kênh → Sao chép mã kênh. ID bắt đầu bằng UC..."
)


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


def parse_feed(xml_text):
    """Channel title and videos from a YouTube RSS (Atom) feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise YouTubeError(f"RSS không đọc được: {e}") from e
    videos = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.findtext("yt:videoId", namespaces=NS)
        if not video_id:
            continue
        link = entry.find("atom:link[@rel='alternate']", NS)
        stats = entry.find("media:group/media:community/media:statistics", NS)
        views = stats.get("views") if stats is not None else None
        videos.append({
            "id": video_id,
            "title": entry.findtext("atom:title", default="", namespaces=NS),
            "published": parse_yt_time(entry.findtext("atom:published", namespaces=NS)),
            "views": int(views) if views and views.isdigit() else None,
            # Shorts come with a /shorts/ link here, which is the exact link to share.
            "link": link.get("href") if link is not None else video_link(video_id),
        })
    return {"title": root.findtext("atom:title", default="", namespaces=NS), "videos": videos}


class YouTubeRSS:
    def __init__(self, session=None):
        self.session = session or ThreadSessions()

    def feed(self, channel_id):
        try:
            resp = self.session.get(RSS_URL, params={"channel_id": channel_id}, timeout=30)
        except requests.RequestException as e:
            raise YouTubeError(f"RSS network error: {e}") from e
        if resp.status_code == 404:
            raise YouTubeError(f"không tìm thấy kênh {channel_id}")
        if resp.status_code != 200:
            raise YouTubeError(f"RSS HTTP {resp.status_code}")
        return parse_feed(resp.text)


class YouTubeClient:
    """YouTube Data API v3. Every call used here costs 1 quota unit."""

    def __init__(self, api_key, session=None, retries=3, backoff_seconds=2.0, sleep=time.sleep):
        self.api_key = api_key
        self.session = session or ThreadSessions()
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep
        self._quota_day = None
        self.units_today = 0

    def _count_unit(self):
        day = datetime.now(QUOTA_TZ).date()
        if day != self._quota_day:
            self._quota_day, self.units_today = day, 0
        self.units_today += 1

    def get(self, endpoint, **params):
        params["key"] = self.api_key
        for attempt in range(self.retries):
            try:
                self._count_unit()
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
        """Stats for any number of videos, 50 per request (1 quota unit each)."""
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


def format_interval(seconds):
    if seconds % 3600 == 0:
        return f"{seconds // 3600} giờ"
    if seconds % 60 == 0:
        return f"{seconds // 60} phút"
    return f"{seconds} giây"


def format_video_message(channel_title, video, threshold, now, format_age):
    lines = [
        f"🔥 Video YouTube vượt {threshold:,} view",
        f"Kênh: {channel_title}",
        f"Tiêu đề: {video['title']}",
        f"Views: {video['views']:,}",
    ]
    if video.get("published"):
        lines.append(f"Đăng cách đây: {format_age(video['published'], now)}")
    lines.append(video.get("link") or video_link(video["id"]))
    return "\n".join(lines)


class YouTubeScanner:
    def __init__(self, cfg, store, telegram, threshold_fn, format_age,
                 rss=None, api=None, clock=time.time, interval_fn=None):
        self.cfg = cfg
        self.interval_fn = interval_fn or (lambda: cfg["youtube_poll_interval_seconds"])
        self.store = store
        self.telegram = telegram
        self.threshold_fn = threshold_fn
        self.format_age = format_age
        self.rss = rss or YouTubeRSS()
        self.api = api
        self.clock = clock
        self.next_due = 0
        self.cooldown_until = 0
        self.last_scan_at = None
        self.last_scan_result = "chưa quét"
        self._key_alert_sent = False

    @property
    def mode(self):
        return "API key + RSS" if self.api else "RSS miễn phí (không cần key)"

    def ready(self, forced=False):
        now = self.clock()
        return now >= self.cooldown_until and (forced or now >= self.next_due)

    def seconds_until_due(self):
        return max(self.next_due, self.cooldown_until) - self.clock()

    # --- channels -------------------------------------------------------------

    def resolve_channel(self, text):
        """{'id', 'title', 'uploads'} or None. Without an API key only IDs work."""
        kind, value = parse_channel_input(text)
        if self.api:
            return self.api.resolve_channel(text)
        if kind != "id":
            return None
        feed = self.rss.feed(value)
        return {"id": value, "title": feed["title"] or value, "uploads": "UU" + value[2:]}

    def seed_channels(self, inputs):
        """Add channels from config once; channels removed via /removeyt stay removed."""
        for text in inputs:
            key = f"yt_seeded:{text}"
            if self.store.get_setting(key):
                continue
            try:
                channel = self.resolve_channel(text)
            except YouTubeError as e:
                log.error("Could not resolve YouTube channel %s: %s", text, e)
                continue
            if not channel:
                log.error("YouTube channel not found: %s (without an API key use the UC... ID)", text)
                continue
            self.store.add_channel(channel["id"], channel["title"], channel["uploads"])
            self.store.set_setting(key, channel["id"])

    def add_channel(self, text):
        kind, _ = parse_channel_input(text)
        if kind == "handle" and not self.api:
            return (
                f"❌ Chưa có YOUTUBE_API_KEY nên không tra được '{text}'. "
                f"Hãy dùng ID kênh (UC...).\n{FIND_CHANNEL_ID_HELP}"
            )
        try:
            channel = self.resolve_channel(text)
        except YouTubeError as e:
            return f"❌ Lỗi YouTube: {e}"
        if not channel:
            return f"❌ Không tìm thấy kênh '{text}'. Dùng @handle, ID kênh (UC...) hoặc link kênh."
        self.store.add_channel(channel["id"], channel["title"], channel["uploads"])
        self.next_due = 0
        return f"✅ Đã thêm kênh {channel['title']} ({channel['id']})"

    # --- scanning -------------------------------------------------------------

    def _discover(self, channel, since):
        """Recent videos of one channel: RSS first, the API fills gaps when it can."""
        channel_id, _, uploads = channel
        try:
            videos = self.rss.feed(channel_id)["videos"]
        except YouTubeError as e:
            if not self.api:
                raise
            log.warning("RSS failed for %s (%s); using the API", channel_id, e)
            videos = []
        recent = [v for v in videos if not v["published"] or v["published"] >= since]
        # RSS only has the newest 15; if all of them are recent there may be more.
        if self.api and uploads and (not videos or len(recent) >= RSS_MAX_ENTRIES):
            known = {v["id"] for v in recent}
            recent += [{"id": vid} for vid in self.api.recent_video_ids(uploads, since)
                       if vid not in known]
        return recent

    def scan_once(self):
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=self.cfg["max_reel_age_days"])
        threshold = self.threshold_fn()
        channels = self.store.active_channels()
        sent = 0
        self.next_due = self.clock() + self.interval_fn()
        try:
            pending = {}  # video_id -> (video, channel_id, channel_title)
            with ThreadPoolExecutor(max_workers=self.cfg["workers"]) as pool:
                results = pool.map(lambda c: (c, self._try_discover(c, since)), channels)
                for (channel_id, title, _), videos in results:
                    for video in videos:
                        if not self.store.yt_was_notified(video["id"]):
                            pending[video["id"]] = (video, channel_id, title)
            if self.api and pending:
                # One request per 50 videos across all channels.
                for fresh in self.api.videos(list(pending)):
                    video = pending[fresh["id"]][0]
                    video.update({k: v for k, v in fresh.items() if v is not None})
            for video, channel_id, title in pending.values():
                if video.get("views") is None:
                    continue
                link = video.get("link") or video_link(video["id"])
                self.store.save_yt_video(video["id"], channel_id, video.get("title", ""),
                                         link, video["views"])
                if video["views"] < threshold:
                    continue
                video["link"] = link
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

        self._key_alert_sent = False
        self.last_scan_at = self.clock()
        self.last_scan_result = f"{len(channels)} kênh, {len(pending)} video, gửi {sent} thông báo"
        log.info("YouTube scan done: %s", self.last_scan_result)
        return sent

    def _try_discover(self, channel, since):
        try:
            return self._discover(channel, since)
        except (QuotaError, ApiKeyError):
            raise
        except YouTubeError as e:
            log.error("Could not list videos for %s: %s", channel[1], e)
            return []

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

    def status_lines(self):
        lines = [
            f"Chế độ: {self.mode}",
            f"Kênh đang theo dõi: {len(self.store.active_channels())}",
            f"Quét mỗi: {format_interval(self.interval_fn())}",
            f"Đã gửi thông báo: {self.store.yt_notified_count()} video",
        ]
        if self.api:
            lines.append(f"Quota đã dùng hôm nay: ~{self.api.units_today:,}/{DAILY_QUOTA:,}")
        return lines
