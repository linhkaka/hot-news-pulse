"""Thông báo khi có hàng đáng xem: Telegram (điện thoại) và thông báo Windows.

Báo khi:
  - video QC Facebook mới vào nhãn Sắp WIN / Video Win;
  - video TikTok / Reels mới vào nhãn Đang nổ / Viral;
  - page/shop đang theo dõi vừa lên QC mới.
Mỗi thứ chỉ báo 1 lần (bảng `notified`). Video đã có từ trước khi bật thông báo được ghi nhận im lặng,
nên bật lên không bị dội hàng trăm tin.
"""
import html
import os
import subprocess

import httpx

from . import db

DEFAULT = {"telegram_token": "", "telegram_chat_id": "", "windows": True,
           "events": {"sap_win": True, "win": True, "viral": True, "follow": True}}
MAX_ITEMS_PER_MESSAGE = 5
TG_API = "https://api.telegram.org"


def settings():
    s = db.get_setting("notify", {})
    return {**DEFAULT, **s, "events": {**DEFAULT["events"], **s.get("events", {})}}


def public_settings():
    """Cho giao diện: không trả nguyên token."""
    s = settings()
    tok = s.pop("telegram_token")
    return {**s, "desktop": s["windows"], "has_token": bool(tok), "token_hint": ("…" + tok[-4:]) if tok else ""}


def save_settings(telegram_token=None, telegram_chat_id=None, windows=None, events=None):
    s = settings()
    if telegram_token is not None and telegram_token.strip() != "":
        s["telegram_token"] = telegram_token.strip()
    if telegram_token == "":                      # gửi chuỗi rỗng có chủ đích = xoá token
        s["telegram_token"] = ""
    if telegram_chat_id is not None:
        s["telegram_chat_id"] = str(telegram_chat_id).strip()
    if windows is not None:
        s["windows"] = bool(windows)
    if events:
        s["events"].update({k: bool(v) for k, v in events.items() if k in DEFAULT["events"]})
    db.set_setting("notify", s)


# ---------------- kênh gửi ----------------

def send_telegram(token, chat_id, text, client=None):
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        r = client.post(f"{TG_API}/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                              "disable_web_page_preview": True})
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or f"Telegram trả lỗi {r.status_code}")
    finally:
        if own:
            client.close()


def find_chat_id(token, client=None):
    """Lấy chat ID từ tin nhắn gần nhất người dùng gửi cho bot (bước 'nhắn /start cho bot')."""
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        data = client.get(f"{TG_API}/bot{token}/getUpdates").json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or "Token không đúng")
        for upd in reversed(data.get("result", [])):
            chat = (upd.get("message") or upd.get("channel_post") or {}).get("chat")
            if chat and chat.get("id") is not None:
                return str(chat["id"])
        return None
    finally:
        if own:
            client.close()


_TOAST_PS = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x = $t.GetElementsByTagName('text')
$x.Item(0).AppendChild($t.CreateTextNode($env:SNAKEPOD_TOAST_TITLE)) > $null
$x.Item(1).AppendChild($t.CreateTextNode($env:SNAKEPOD_TOAST_BODY)) > $null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($t))
"""


def windows_toast(title, body):
    """Thông báo góc màn hình Windows 10/11 (không cần cài thêm gì). Nội dung truyền qua biến môi trường."""
    if os.name != "nt" or os.environ.get("SNAKEPOD_NO_TOAST") == "1":
        return False
    env = {**os.environ, "SNAKEPOD_TOAST_TITLE": title[:120], "SNAKEPOD_TOAST_BODY": body[:250]}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", _TOAST_PS],
                   env=env, timeout=20, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def send(title, lines, log=print, client=None):
    """Gửi 1 thông báo tới mọi kênh đang bật. Lỗi 1 kênh không chặn kênh khác."""
    s = settings()
    sent = []
    if s["telegram_token"] and s["telegram_chat_id"]:
        text = f"<b>{html.escape(title)}</b>\n" + "\n".join(lines)
        try:
            send_telegram(s["telegram_token"], s["telegram_chat_id"], text, client)
            sent.append("telegram")
        except Exception as e:
            log(f"Không gửi được Telegram: {e}")
    if s["windows"]:
        try:
            if windows_toast(title, _plain(lines[0]) if lines else ""):
                sent.append("windows")
        except Exception as e:
            log(f"Không hiện được thông báo Windows: {e}")
    return sent


def _plain(line):
    import re
    return html.unescape(re.sub(r"<[^>]+>", "", line))


# ---------------- phát hiện cái mới ----------------

def _fresh(kind, keys):
    """Trong `keys`, những cái chưa từng báo. Đồng thời đánh dấu tất cả là đã báo."""
    keys = list(dict.fromkeys(keys))
    new = db.unseen_notified(kind, keys)
    db.mark_notified(kind, keys)
    return new


def _link(url, text):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>' if url else html.escape(text)


def _batch(title, items, fmt, log, client):
    if not items:
        return []
    lines = [fmt(v) for v in items[:MAX_ITEMS_PER_MESSAGE]]
    if len(items) > MAX_ITEMS_PER_MESSAGE:
        lines.append(f"… và {len(items) - MAX_ITEMS_PER_MESSAGE} video khác (mở SNAKEMEDIA POD để xem)")
    return send(f"{title} ({len(items)})", lines, log, client)


def check_videos(videos, log=print, client=None):
    """Gọi sau mỗi lần chấm lại video QC Facebook."""
    ev = settings()["events"]
    out = []
    for label, name in (("sap_win", "Sắp WIN mới"), ("win", "Video Win mới")):
        cur = [v for v in videos if v["label"] == label]
        new_ids = set(_fresh(label, [v["cid"] for v in cur]))
        new = [v for v in cur if v["cid"] in new_ids]
        if ev.get(label) and new:
            out += _batch(f"🐍 {name}", new, lambda v: (
                f"• {_link(v.get('ad_library_url'), v['title'][:80])} — video {v.get('video_age_days') or '?'} ngày, "
                f"{v['shops_active']} shop, {v['ads_per_day']} QC/ngày"), log, client)
    return out


def check_social(items, log=print, client=None):
    """Gọi sau mỗi lần quét video viral. `items` là kết quả social.summarize()."""
    ev = settings()["events"]
    cur = [v for v in items if v["label"] in ("dang_no", "viral")]
    new_ids = set(_fresh("viral", [v["vid"] for v in cur]))
    new = sorted((v for v in cur if v["vid"] in new_ids), key=lambda v: v.get("sort_vph") or 0, reverse=True)
    if not (ev.get("viral") and new):
        return []
    return _batch("🔥 Video viral mới", new, lambda v: (
        f"• {_link(v.get('url'), (v.get('caption') or 'video')[:80])} — {v.get('views') or '?'} xem, "
        f"{v.get('vph') or '?'}/giờ"), log, client)


def follow_update(name, new_ads, log=print, client=None):
    if new_ads and settings()["events"].get("follow"):
        return send(f"★ {name} vừa lên {new_ads} QC mới", [html.escape("Mở mục Theo dõi đặc biệt để xem.")], log, client)
    return []
