"""Facebook Reels + YouTube -> Telegram tracker (official APIs only).

Polls the Reels of Facebook Pages you manage (Graph API) and the videos of
YouTube channels (RSS feed + optional YouTube Data API), and sends the link
to a Telegram chat the first time a Reel or video crosses the view threshold.
Pages and channels are scanned in parallel. The tracker is also controlled
from Telegram (/add, /addall, /addyt, /threshold, /top, /status ...).

Usage:
    python tracker.py                   # run forever (bot + scanner)
    python tracker.py --once            # one scan and exit (good for cron)
    python tracker.py --test-telegram   # send a test message and exit
"""

import argparse
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

from config import facebook_enabled, load_config
from graph import GraphAPIError, GraphClient, RateLimitError, TokenError, parse_fb_time
from report import ScanReport, format_report, snapshots_csv
from store import Store
from telegram_bot import CommandBot, Telegram, TelegramError
from youtube import YouTubeClient, YouTubeScanner, format_interval

log = logging.getLogger("reels_tracker")

PAGE_TOKEN_REFRESH_SECONDS = 30 * 60
RATE_LIMIT_COOLDOWN_SECONDS = 15 * 60
TOKEN_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
FB_DISABLED = "Facebook chưa bật. Thêm FB_USER_ACCESS_TOKEN vào file .env rồi chạy lại tool."


def reel_link(reel):
    link = reel.get("permalink_url") or f"/reel/{reel['id']}"
    if link.startswith("/"):
        link = "https://www.facebook.com" + link
    return link


def format_age(created, now):
    minutes = int((now - created).total_seconds() // 60)
    hours, minutes = divmod(max(minutes, 0), 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days} ngày {hours} giờ"
    if hours:
        return f"{hours} giờ {minutes} phút"
    return f"{minutes} phút"


def format_message(page_name, reel, views, threshold, now=None):
    now = now or datetime.now(timezone.utc)
    caption = (reel.get("description") or "").strip()
    if len(caption) > 120:
        caption = caption[:117] + "..."
    lines = [
        f"🔥 Reel vượt {threshold:,} view",
        f"Page: {page_name}",
        f"Views: {views:,}",
    ]
    created = parse_fb_time(reel.get("created_time"))
    if created:
        lines.append(f"Đăng cách đây: {format_age(created, now)}")
    if caption:
        lines.append(f"Caption: {caption}")
    lines.append(reel_link(reel))
    return "\n".join(lines)


# Set from the config in main(); messages show times in this zone.
DISPLAY_TZ = timezone(timedelta(hours=7))


def format_time(ts):
    return datetime.fromtimestamp(ts, DISPLAY_TZ).strftime("%H:%M %d/%m/%Y")


class Tracker:
    def __init__(self, cfg, graph, telegram, store, clock=time.time):
        self.cfg = cfg
        self.facebook_enabled = facebook_enabled(cfg)
        self.youtube = None  # YouTubeScanner, set in main()
        self.fb_next_due = 0
        self.graph = graph
        self.telegram = telegram
        self.store = store
        self.clock = clock
        # scan_requested forces a scan now; wakeup only makes the loop re-plan.
        self.scan_requested = threading.Event()
        self.wakeup = threading.Event()
        self.last_scan_at = None
        self.last_scan_result = "chưa quét"
        self.cooldown_until = 0
        self.token_expires_at = None
        self._managed = {}
        self._managed_at = None
        self._token_alert_sent = False
        self._last_token_check = None
        self._warned_missing = set()
        # reel_id -> clock() of the last view check, for the slow lane of older Reels.
        self._last_checked = {}
        self.last_report = None  # ScanReport of the latest successful Facebook scan

    def threshold(self):
        return int(self.store.get_setting("view_threshold", self.cfg["view_threshold"]))

    def scan_interval(self, cfg_key="poll_interval_seconds"):
        """Seconds between scans; /interval overrides the config for both platforms."""
        return int(self.store.get_setting("scan_interval_seconds", self.cfg[cfg_key]))

    def request_scan(self):
        self.scan_requested.set()
        self.wakeup.set()

    def set_scan_interval(self, seconds):
        """Apply a new interval right away, counted from the last scan."""
        self.store.set_setting("scan_interval_seconds", seconds)
        self.fb_next_due = (self.last_scan_at or self.clock()) + seconds
        if self.youtube:
            self.youtube.next_due = (self.youtube.last_scan_at or self.clock()) + seconds
        self.wakeup.set()

    def managed_pages(self, force=False):
        """page_id -> (name, page token) for Pages the user token manages (cached)."""
        if not self.cfg["user_access_token"]:
            return {}
        stale = (
            self._managed_at is None
            or self.clock() - self._managed_at > PAGE_TOKEN_REFRESH_SECONDS
        )
        if force or stale:
            self._managed = self.graph.page_tokens_from_user_token(self.cfg["user_access_token"])
            self._managed_at = self.clock()
        return self._managed

    def pages_with_tokens(self):
        """Active Pages as (page_id, name, token); Pages without a token are skipped."""
        managed = self.managed_pages()
        pages = []
        for page_id, name, own_token in self.store.active_pages():
            managed_name, managed_token = managed.get(page_id, (None, None))
            token = own_token or managed_token
            if not token:
                if page_id not in self._warned_missing:
                    log.warning(
                        "No access token for Page %s: you must be an admin of it "
                        "(or set 'access_token' for it in the config). Skipping.",
                        page_id,
                    )
                    self._warned_missing.add(page_id)
                continue
            if not name and managed_name:
                name = managed_name
                self.store.set_page_name(page_id, name)
            pages.append((page_id, name or page_id, token))
        return pages

    def add_page(self, page_id):
        if not self.facebook_enabled:
            return FB_DISABLED
        if not page_id.isdigit():
            return f"❌ '{page_id}' không phải Page ID (Page ID là một dãy số)."
        try:
            managed = self.managed_pages(force=True)
        except GraphAPIError as e:
            return f"❌ Lỗi Facebook API: {e}"
        if page_id not in managed:
            return (
                f"❌ Không đọc được Page {page_id}. Chỉ thêm được Page bạn quản lý "
                "và token có quyền — xem danh sách bằng /mypages."
            )
        name = managed[page_id][0]
        self.store.add_page(page_id, name)
        self._warned_missing.discard(page_id)
        self.request_scan()
        return f"✅ Đã thêm {name} ({page_id})"

    def add_all_pages(self):
        if not self.facebook_enabled:
            return FB_DISABLED
        try:
            managed = self.managed_pages(force=True)
        except GraphAPIError as e:
            return f"❌ Lỗi Facebook API: {e}"
        if not managed:
            return "Token hiện tại không quản lý Page nào."
        tracked = {pid for pid, _, _ in self.store.active_pages()}
        added = [(pid, name) for pid, (name, _) in managed.items() if pid not in tracked]
        for page_id, name in added:
            self.store.add_page(page_id, name)
            self._warned_missing.discard(page_id)
        self.request_scan()
        if not added:
            return f"Tất cả {len(managed)} Page bạn quản lý đã được theo dõi."
        return f"✅ Đã thêm {len(added)} Page:\n" + "\n".join(f"• {n} ({pid})" for pid, n in added)

    def my_pages_text(self):
        if not self.facebook_enabled:
            return FB_DISABLED
        try:
            managed = self.managed_pages(force=True)
        except GraphAPIError as e:
            return f"❌ Lỗi Facebook API: {e}"
        if not managed:
            return "Token hiện tại không quản lý Page nào."
        tracked = {pid for pid, _, _ in self.store.active_pages()}
        lines = ["📄 Page bạn quản lý (✅ = đang theo dõi):"]
        for page_id, (name, _) in sorted(managed.items(), key=lambda kv: kv[1][0]):
            mark = "✅" if page_id in tracked else "➕"
            lines.append(f"{mark} {name} — {page_id}")
        lines.append("\nThêm 1 Page: /add <page_id> — thêm tất cả: /addall")
        return "\n".join(lines)

    def status_text(self):
        lines = [
            "📊 Trạng thái Tracker",
            f"Ngưỡng: {self.threshold():,} view",
            f"Theo dõi nội dung đăng trong: {self.cfg['max_reel_age_days']} ngày",
        ]
        if self.facebook_enabled:
            lines += self._facebook_status_lines()
        if self.youtube:
            lines += self._youtube_status_lines()
        return "\n".join(lines)

    def _youtube_status_lines(self):
        yt = self.youtube
        lines = ["", "▶️ YouTube", *yt.status_lines()]
        if yt.last_scan_at:
            lines.append(f"Lần quét gần nhất: {format_time(yt.last_scan_at)} ({yt.last_scan_result})")
        else:
            lines.append(f"Lần quét gần nhất: {yt.last_scan_result}")
        if yt.cooldown_until > self.clock():
            lines.append(f"⏸ Tạm dừng do hết quota đến {format_time(yt.cooldown_until)}")
        return lines

    def _facebook_status_lines(self):
        lines = [
            "",
            "📘 Facebook Reels",
            f"Page đang theo dõi: {len(self.store.active_pages())}",
            f"Quét mỗi: {format_interval(self.scan_interval())}",
            f"Đã gửi thông báo: {self.store.notified_count()} Reel",
        ]
        if self.last_scan_at:
            lines.append(f"Lần quét gần nhất: {format_time(self.last_scan_at)} ({self.last_scan_result})")
        else:
            lines.append(f"Lần quét gần nhất: {self.last_scan_result}")
        if self.cooldown_until > self.clock():
            lines.append(f"⏸ Tạm dừng do giới hạn API đến {format_time(self.cooldown_until)}")
        if self.token_expires_at == 0:
            lines.append("Token Facebook: không hết hạn")
        elif self.token_expires_at:
            lines.append(f"Token Facebook hết hạn: {format_time(self.token_expires_at)}")
        return lines

    def _send_token_alert(self, text):
        if self._token_alert_sent:
            return
        self._token_alert_sent = True
        log.error(text)
        try:
            self.telegram.send(text)
        except (TelegramError, requests.RequestException) as e:
            log.warning("Could not send token alert: %s", e)

    def check_token_expiry(self):
        token = self.cfg["user_access_token"]
        now = self.clock()
        if not token or (
            self._last_token_check is not None
            and now - self._last_token_check < TOKEN_CHECK_INTERVAL_SECONDS
        ):
            return
        self._last_token_check = now
        try:
            expires_at = self.graph.token_expires_at(token)
        except TokenError as e:
            self._send_token_alert(f"⚠️ Token Facebook không còn hợp lệ ({e}). Hãy lấy token mới.")
            return
        self.token_expires_at = expires_at
        if expires_at and expires_at - now < self.cfg["token_warning_days"] * 86400:
            days_left = max(0, int((expires_at - now) // 86400))
            try:
                self.telegram.send(
                    f"⏰ Token Facebook sẽ hết hạn sau {days_left} ngày "
                    f"({format_time(expires_at)}). Hãy lấy token mới (README Bước 2)."
                )
            except (TelegramError, requests.RequestException) as e:
                log.warning("Could not send expiry warning: %s", e)

    def _due_for_check(self, reel):
        """Reels older than `fresh_hours` are re-checked at most every slow interval."""
        created = parse_fb_time(reel.get("created_time"))
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600 if created else 0
        if age_hours <= self.cfg["fresh_hours"]:
            return True
        last = self._last_checked.get(reel["id"])
        return last is None or self.clock() - last >= self.cfg["slow_check_interval_seconds"]

    def _scan_page(self, page, since, threshold, now, abort, report):
        """Check one Page; returns (alerts sent, Reels checked, Reel ids seen)."""
        page_id, page_name, token = page
        try:
            reels = self.graph.recent_reels(page_id, token, since)
        except (RateLimitError, TokenError):
            abort.set()
            raise
        except GraphAPIError as e:
            log.error("Could not list Reels for %s: %s", page_name, e)
            report.mark_error(page_id, e)
            return 0, 0, set()
        log.debug("%s: %d recent Reels", page_name, len(reels))
        sent = checked = 0
        seen = {reel["id"] for reel in reels}
        for reel in reels:
            if abort.is_set():
                break
            link = reel_link(reel)
            prev = self.store.last_views("facebook", reel["id"])
            if not self._due_for_check(reel):
                # Slow lane: report the last known views without a new API call.
                if prev is not None:
                    report.add_item(page_id, reel["id"], reel.get("description"), link,
                                    parse_fb_time(reel.get("created_time")), prev, prev)
                continue
            try:
                views = self.graph.reel_views(reel["id"], token, self.cfg["view_metrics"])
            except (RateLimitError, TokenError):
                abort.set()
                raise
            self._last_checked[reel["id"]] = self.clock()
            checked += 1
            if views is None:
                log.debug("No view metric for Reel %s", reel["id"])
                continue
            self.store.save_reel(reel["id"], page_id, link, reel.get("description"), views)
            report.add_item(page_id, reel["id"], reel.get("description"), link,
                            parse_fb_time(reel.get("created_time")), views, prev)
            if views < threshold or self.store.was_notified(reel["id"]):
                continue
            try:
                self.telegram.send(format_message(page_name, reel, views, threshold, now))
            except (TelegramError, requests.RequestException) as e:
                log.error("Telegram send failed for Reel %s: %s", reel["id"], e)
                continue
            self.store.mark_notified(reel["id"], page_id, views, link)
            sent += 1
            log.info("Notified Reel %s (%d views)", reel["id"], views)
        return sent, checked, seen

    def scan_once(self):
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=self.cfg["max_reel_age_days"])
        threshold = self.threshold()
        sent = checked = 0
        seen = set()
        abort = threading.Event()
        report = ScanReport("facebook", now)
        try:
            pages = self.pages_with_tokens()
            for page_id, page_name, _ in pages:
                report.add_source(page_id, page_name,
                                  self.store.source_scanned_before("facebook", page_id))
            fatal = None
            with ThreadPoolExecutor(max_workers=self.cfg["workers"]) as pool:
                futures = [pool.submit(self._scan_page, p, since, threshold, now, abort, report)
                           for p in pages]
                for future in as_completed(futures):
                    try:
                        page_sent, page_checked, page_seen = future.result()
                    except (RateLimitError, TokenError) as e:
                        fatal = fatal or e
                        continue
                    sent += page_sent
                    checked += page_checked
                    seen |= page_seen
            if fatal:
                raise fatal
        except RateLimitError as e:
            self.cooldown_until = self.clock() + RATE_LIMIT_COOLDOWN_SECONDS
            self.last_scan_result = "bị Facebook giới hạn tốc độ, tạm nghỉ 15 phút"
            log.warning("Rate limited by Graph API (%s); pausing scans", e)
            return sent
        except TokenError as e:
            self.last_scan_result = "lỗi token Facebook"
            self._send_token_alert(
                f"⚠️ Token Facebook không hợp lệ hoặc đã hết hạn ({e}).\n"
                "Hãy lấy token mới (README Bước 2b) rồi khởi động lại tool."
            )
            return sent
        except GraphAPIError as e:
            self.last_scan_result = f"lỗi: {e}"
            log.error("Scan failed: %s", e)
            return sent

        # Forget Reels that dropped out of the time window.
        self._last_checked = {k: v for k, v in self._last_checked.items() if k in seen}
        for page_id, _, _ in pages:
            self.store.mark_source_scanned("facebook", page_id)
        self.last_report = report
        self._token_alert_sent = False
        self.last_scan_at = self.clock()
        self.last_scan_result = f"{len(pages)} Page, {checked} Reel, gửi {sent} thông báo"
        log.info("Facebook scan done: %s", self.last_scan_result)
        return sent

    def run(self, stop_event, once=False):
        while not stop_event.is_set():
            forced = once or self.scan_requested.is_set()
            self.scan_requested.clear()
            now = self.clock()
            reports = []
            if (
                self.facebook_enabled
                and now >= self.cooldown_until
                and (forced or now >= self.fb_next_due)
            ):
                self.check_token_expiry()
                self.last_report = None
                self.scan_once()
                self.fb_next_due = self.clock() + self.scan_interval()
                reports.append(self.last_report)
            if self.youtube and self.youtube.ready(forced):
                self.youtube.last_report = None
                self.youtube.scan_once()
                reports.append(self.youtube.last_report)
            self.publish_reports([r for r in reports if r is not None])
            if once:
                return
            self.wakeup.wait(max(1, self._seconds_until_next_scan()))
            self.wakeup.clear()

    def auto_report(self):
        return self.store.get_setting("auto_report", "1") == "1"

    def publish_reports(self, reports):
        """Save this scan round's views to the history and send the report."""
        if not reports:
            return
        for report in reports:
            self.store.add_snapshots(report.snapshot_rows())
        keep_from = datetime.now(timezone.utc) - timedelta(days=self.cfg["history_days"])
        self.store.prune_snapshots(keep_from.isoformat())
        text = format_report(reports, self.cfg["report_top_videos"], format_time(self.clock()))
        self.store.set_setting("last_report", text)
        if not self.auto_report():
            return
        try:
            self.telegram.send_long(text)
        except (TelegramError, requests.RequestException) as e:
            log.warning("Could not send views report: %s", e)

    def export_csv(self, days):
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.store.snapshots_since(since.isoformat())
        return snapshots_csv(rows), len(rows)

    def _seconds_until_next_scan(self):
        waits = []
        if self.facebook_enabled:
            waits.append(max(self.fb_next_due, self.cooldown_until) - self.clock())
        if self.youtube:
            waits.append(self.youtube.seconds_until_due())
        return min(waits) if waits else 60


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test message")
    parser.add_argument("--no-bot", action="store_true", help="Don't answer Telegram commands")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        cfg = load_config(args.config)
    except (ValueError, OSError) as e:
        log.error("Lỗi cấu hình: %s", e)
        return 2

    global DISPLAY_TZ
    DISPLAY_TZ = timezone(timedelta(hours=cfg["utc_offset_hours"]))
    telegram = Telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"])
    if args.test_telegram:
        try:
            telegram.send("✅ Tracker: kết nối Telegram thành công!")
        except (TelegramError, requests.RequestException) as e:
            log.error("Không gửi được tin Telegram: %s", e)
            return 1
        log.info("Test message sent")
        return 0

    graph = GraphClient(cfg["graph_api_version"])
    store = Store(cfg["db_path"])
    store.seed_pages(cfg["pages"])
    tracker = Tracker(cfg, graph, telegram, store)
    api = YouTubeClient(cfg["youtube_api_key"]) if cfg["youtube_api_key"] else None
    tracker.youtube = YouTubeScanner(
        cfg, store, telegram, tracker.threshold, format_age, api=api,
        interval_fn=lambda: tracker.scan_interval("youtube_poll_interval_seconds"),
    )
    tracker.youtube.seed_channels(cfg["youtube_channels"])
    stop = threading.Event()

    if args.once:
        tracker.run(stop, once=True)
        return 0

    if not args.no_bot:
        try:
            telegram.set_commands()
        except (TelegramError, requests.RequestException) as e:
            log.warning("Could not register bot commands: %s", e)
        threading.Thread(target=CommandBot(telegram, tracker).run, args=(stop,), daemon=True).start()

    lines = [
        f"🚀 Tracker đã chạy — ngưỡng {tracker.threshold():,} view, "
        f"quét mỗi {format_interval(tracker.scan_interval())}."
    ]
    if tracker.facebook_enabled:
        page_count = len(store.active_pages())
        lines.append(f"📘 Facebook: {page_count} Page")
        if not page_count:
            lines.append("   Chưa có Page nào — gõ /addall để thêm tất cả Page bạn quản lý.")
    channel_count = len(store.active_channels())
    lines.append(f"▶️ YouTube: {channel_count} kênh ({tracker.youtube.mode})")
    if not channel_count:
        example = "@handle_kenh" if api else "UCxxxxxxxx (ID kênh)"
        lines.append(f"   Chưa có kênh nào — gõ /addyt {example}.")
    lines.append("Gõ /help để xem lệnh.")
    try:
        telegram.send("\n".join(lines))
    except (TelegramError, requests.RequestException) as e:
        log.warning("Could not send startup message: %s", e)

    try:
        tracker.run(stop)
    except KeyboardInterrupt:
        log.info("Stopped")
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
