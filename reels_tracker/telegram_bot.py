"""Telegram: sending alerts and handling chat commands that control the tracker."""

import logging
import threading
import time
from datetime import datetime

import requests

from net import ThreadSessions

log = logging.getLogger("reels_tracker.telegram")

COMMANDS = [
    ("status", "Trạng thái tool"),
    ("pages", "Danh sách Page đang theo dõi"),
    ("add", "Thêm Page: /add <page_id>"),
    ("addall", "Thêm tất cả Page bạn quản lý"),
    ("remove", "Bỏ Page: /remove <page_id>"),
    ("mypages", "Các Page bạn quản lý (có thể /add)"),
    ("channels", "Kênh YouTube đang theo dõi"),
    ("addyt", "Thêm kênh YouTube: /addyt @handle"),
    ("removeyt", "Bỏ kênh YouTube: /removeyt <channel_id>"),
    ("threshold", "Đổi ngưỡng view: /threshold 5000"),
    ("interval", "Đổi thời gian quét: /interval 30 (phút)"),
    ("report", "Báo cáo view lần quét gần nhất (/report on|off)"),
    ("export", "Tải file Excel lịch sử view: /export 7 (ngày)"),
    ("top", "Top Reels/video nhiều view nhất"),
    ("scan", "Quét ngay"),
    ("help", "Hướng dẫn"),
]


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, bot_token, chat_id, session=None):
        self.api = f"https://api.telegram.org/bot{bot_token}"
        self.chat_id = str(chat_id)
        self.session = session or ThreadSessions()
        # Scans send alerts from several threads; keep messages in order.
        self._send_lock = threading.Lock()

    def _call(self, method, payload, timeout=30):
        resp = self.session.post(f"{self.api}/{method}", json=payload, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(f"Telegram {method} failed: {data.get('description')}")
        return data["result"]

    def send(self, text, chat_id=None):
        # Telegram rejects messages longer than 4096 characters.
        with self._send_lock:
            self._call("sendMessage", {"chat_id": chat_id or self.chat_id, "text": text[:4096]})

    def send_long(self, text, limit=4000):
        """Send text of any length, split at line breaks into several messages."""
        chunk = ""
        for line in text.split("\n"):
            if chunk and len(chunk) + len(line) + 1 > limit:
                self.send(chunk)
                chunk = ""
            chunk = f"{chunk}\n{line}" if chunk else line
        if chunk:
            self.send(chunk)

    def send_document(self, filename, content, caption=""):
        with self._send_lock:
            resp = self.session.post(
                f"{self.api}/sendDocument",
                data={"chat_id": self.chat_id, "caption": caption},
                files={"document": (filename, content)},
                timeout=60,
            )
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(f"Telegram sendDocument failed: {data.get('description')}")

    def get_updates(self, offset, timeout=50):
        return self._call(
            "getUpdates",
            {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
            timeout=timeout + 10,
        )

    def set_commands(self):
        self._call(
            "setMyCommands",
            {"commands": [{"command": c, "description": d} for c, d in COMMANDS]},
        )


HELP_TEXT = "🤖 Reels & YouTube Tracker — các lệnh:\n" + "\n".join(f"/{c} — {d}" for c, d in COMMANDS)


class CommandBot:
    """Answers commands sent from the configured chat; ignores everyone else."""

    def __init__(self, telegram, tracker):
        self.telegram = telegram
        self.tracker = tracker

    def handle(self, text):
        parts = text.strip().split()
        if not parts or not parts[0].startswith("/"):
            return None
        command = parts[0][1:].split("@")[0].lower()
        args = parts[1:]
        t = self.tracker

        if command in ("start", "help"):
            return HELP_TEXT
        if command == "status":
            return t.status_text()
        if command == "pages":
            pages = t.store.active_pages()
            if not pages:
                return "Chưa theo dõi Page nào. Dùng /mypages rồi /add <page_id>."
            return "📋 Page đang theo dõi:\n" + "\n".join(
                f"• {name or pid} ({pid})" for pid, name, _ in pages
            )
        if command == "mypages":
            return t.my_pages_text()
        if command == "addall":
            return t.add_all_pages()
        if command == "add":
            if not args:
                return "Cách dùng: /add <page_id>  (xem ID bằng /mypages)"
            return "\n".join(t.add_page(page_id) for page_id in args)
        if command == "remove":
            if not args:
                return "Cách dùng: /remove <page_id>"
            return "\n".join(
                f"🗑 Đã bỏ Page {pid}" if t.store.remove_page(pid) else f"Không thấy Page {pid}"
                for pid in args
            )
        if command == "channels":
            channels = t.store.active_channels()
            if not channels:
                return "Chưa theo dõi kênh YouTube nào. Dùng /addyt @handle hoặc /addyt UC..."
            return "▶️ Kênh YouTube đang theo dõi:\n" + "\n".join(
                f"• {title} ({cid})" for cid, title, _ in channels
            )
        if command == "addyt":
            if not args:
                return ("Cách dùng: /addyt @handle  (hoặc ID kênh UC..., hoặc link kênh)\n"
                        "Thêm nhiều kênh: /addyt UCaaa UCbbb")
            replies = [t.youtube.add_channel(arg) for arg in args]
            t.request_scan()
            return "\n".join(replies)
        if command == "removeyt":
            if not args:
                return "Cách dùng: /removeyt <channel_id>  (xem ID bằng /channels)"
            return "\n".join(
                f"🗑 Đã bỏ kênh {cid}" if t.store.remove_channel(cid) else f"Không thấy kênh {cid}"
                for cid in args
            )
        if command == "threshold":
            if not args or not args[0].isdigit() or int(args[0]) <= 0:
                return f"Ngưỡng hiện tại: {t.threshold():,} view.\nĐổi: /threshold 5000"
            t.store.set_setting("view_threshold", int(args[0]))
            return f"✅ Ngưỡng mới: {int(args[0]):,} view"
        if command == "top":
            rows = [("📘", *r) for r in t.store.top_reels(10)]
            rows += [("▶️", *r) for r in t.store.top_videos(10)]
            rows.sort(key=lambda r: r[1], reverse=True)
            if not rows:
                return "Chưa có dữ liệu. Đợi lần quét đầu tiên nhé."
            return "🏆 Top Reels/video:\n" + "\n".join(
                f"{i}. {icon} {views:,} view — {source}\n   {link}"
                for i, (icon, views, link, source) in enumerate(rows[:10], 1)
            )
        if command == "report":
            if args and args[0].lower() in ("on", "off"):
                t.store.set_setting("auto_report", "1" if args[0].lower() == "on" else "0")
                return ("✅ Sẽ gửi báo cáo sau mỗi lần quét." if args[0].lower() == "on"
                        else "🔕 Tắt báo cáo tự động. Gõ /report để xem khi cần.")
            text = t.store.get_setting("last_report")
            if not text:
                return "Chưa có báo cáo. Đợi lần quét đầu tiên hoặc gõ /scan."
            t.telegram.send_long(text)
            return None
        if command == "export":
            days = int(args[0]) if args and args[0].isdigit() and int(args[0]) > 0 else 7
            content, count = t.export_csv(days)
            if not count:
                return "Chưa có dữ liệu lịch sử. Đợi lần quét đầu tiên hoặc gõ /scan."
            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            t.telegram.send_document(
                f"lich_su_view_{stamp}.csv", content,
                f"📁 Lịch sử view {days} ngày gần nhất ({count} dòng). Mở bằng Excel/Google Sheets.",
            )
            return None
        if command == "interval":
            if not args or not args[0].isdigit() or not 1 <= int(args[0]) <= 1440:
                minutes = t.scan_interval() / 60
                return (f"Đang quét mỗi {minutes:g} phút.\n"
                        "Đổi: /interval 30 (30 phút) hoặc /interval 60 (1 giờ)")
            t.set_scan_interval(int(args[0]) * 60)
            return f"✅ Từ giờ quét mỗi {int(args[0])} phút (cả Facebook và YouTube)."
        if command == "scan":
            t.request_scan()
            return "🔄 Đang quét, có kết quả sẽ báo ngay."
        return "Không hiểu lệnh này. Gõ /help để xem danh sách lệnh."

    def run(self, stop_event):
        offset = None
        while not stop_event.is_set():
            try:
                updates = self.telegram.get_updates(offset)
            except (TelegramError, requests.RequestException, ValueError) as e:
                log.warning("getUpdates failed: %s", e)
                time.sleep(5)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat_id = str(message.get("chat", {}).get("id", ""))
                text = message.get("text") or ""
                if chat_id != self.telegram.chat_id:
                    if text:
                        log.info("Ignoring message from unauthorized chat %s", chat_id)
                    continue
                try:
                    reply = self.handle(text)
                except Exception:  # keep the bot alive whatever a command does
                    log.exception("Command %r failed", text)
                    reply = "⚠️ Có lỗi khi xử lý lệnh, xem log để biết chi tiết."
                if reply:
                    try:
                        self.telegram.send(reply)
                    except (TelegramError, requests.RequestException) as e:
                        log.warning("Reply failed: %s", e)
