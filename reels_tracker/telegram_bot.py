"""Telegram: sending alerts and handling chat commands that control the tracker."""

import logging
import time

import requests

log = logging.getLogger("reels_tracker.telegram")

COMMANDS = [
    ("status", "Trạng thái tool"),
    ("pages", "Danh sách Page đang theo dõi"),
    ("add", "Thêm Page: /add <page_id>"),
    ("remove", "Bỏ Page: /remove <page_id>"),
    ("mypages", "Các Page bạn quản lý (có thể /add)"),
    ("channels", "Kênh YouTube đang theo dõi"),
    ("addyt", "Thêm kênh YouTube: /addyt @handle"),
    ("removeyt", "Bỏ kênh YouTube: /removeyt <channel_id>"),
    ("threshold", "Đổi ngưỡng view: /threshold 5000"),
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
        self.session = session or requests.Session()

    def _call(self, method, payload, timeout=30):
        resp = self.session.post(f"{self.api}/{method}", json=payload, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(f"Telegram {method} failed: {data.get('description')}")
        return data["result"]

    def send(self, text, chat_id=None):
        # Telegram rejects messages longer than 4096 characters.
        self._call("sendMessage", {"chat_id": chat_id or self.chat_id, "text": text[:4096]})

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


YT_DISABLED = "YouTube chưa bật. Thêm YOUTUBE_API_KEY vào file .env rồi chạy lại tool."


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
            if not t.youtube:
                return YT_DISABLED
            channels = t.store.active_channels()
            if not channels:
                return "Chưa theo dõi kênh YouTube nào. Dùng /addyt @handle."
            return "▶️ Kênh YouTube đang theo dõi:\n" + "\n".join(
                f"• {title} ({cid})" for cid, title, _ in channels
            )
        if command == "addyt":
            if not t.youtube:
                return YT_DISABLED
            if not args:
                return "Cách dùng: /addyt @handle  (hoặc ID kênh UC..., hoặc link kênh)"
            replies = [t.youtube.add_channel(arg) for arg in args]
            t.scan_requested.set()
            return "\n".join(replies)
        if command == "removeyt":
            if not t.youtube:
                return YT_DISABLED
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
        if command == "scan":
            t.scan_requested.set()
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
