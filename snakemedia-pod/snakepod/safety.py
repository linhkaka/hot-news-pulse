"""Chế độ an toàn: quét như một người dùng bình thường, và DỪNG NGAY khi nền tảng nghi ngờ.

Tool không che giấu việc tự động hoá (không giả dấu vân tay, không giải captcha, không xoay tài khoản).
Thay vào đó nó giảm nguy cơ bị checkpoint bằng cách:
  - nghỉ tối thiểu giữa 2 lần quét cùng nền tảng, cuộn trang chậm có ngẫu nhiên;
  - giới hạn số lần quét mỗi ngày;
  - phát hiện trang checkpoint / captcha / bắt đăng nhập -> tạm dừng mọi lượt quét của nền tảng đó
    cho tới khi bạn tự xác minh trên trình duyệt và bấm "Đã xử lý, quét tiếp".
"""
import time
from datetime import datetime

from . import db

PLATFORMS = {"facebook": "Facebook", "tiktok": "TikTok"}
DEFAULT_LIMITS = {
    "facebook": {"min_gap_s": 90, "max_per_day": 40},
    "tiktok": {"min_gap_s": 150, "max_per_day": 20},
}
# Phần tử captcha phổ biến (Facebook, TikTok, reCAPTCHA, hCaptcha)
CAPTCHA_SELECTOR = ('[id*="captcha" i], [class*="captcha" i], iframe[src*="captcha" i], '
                    'iframe[src*="recaptcha" i], iframe[src*="hcaptcha" i]')


class CheckpointError(Exception):
    def __init__(self, platform, reason, url=None):
        super().__init__(reason)
        self.platform, self.reason, self.url = platform, reason, url


class Skipped(Exception):
    """Lượt quét bị bỏ qua có chủ đích (đang tạm dừng / hết lượt trong ngày)."""


def platform_of(source):
    """'fb_reels', 'tiktok_ads', 'keyword'... -> 'facebook' | 'tiktok'."""
    return "tiktok" if str(source).startswith("tiktok") else "facebook"


def detect(platform, url, title="", has_captcha=False):
    """Trả về lý do (tiếng Việt) nếu trang đang là checkpoint / captcha / bắt đăng nhập, ngược lại None."""
    u, t = (url or "").lower(), (title or "").lower()
    name = PLATFORMS[platform]
    if platform == "facebook":
        if "/checkpoint" in u or "security check" in t or "kiểm tra bảo mật" in t:
            return "Facebook yêu cầu xác minh tài khoản (checkpoint)"
        if "two_step_verification" in u or "/two_factor" in u or "/challenge" in u:
            return "Facebook yêu cầu xác minh 2 bước"
        if "/login" in u or "login.php" in u:
            return "Facebook yêu cầu đăng nhập lại"
    else:
        if "/login" in u:
            return "TikTok yêu cầu đăng nhập lại"
        if "verify" in t and "tiktok" in t:
            return "TikTok yêu cầu xác minh"
    if has_captcha:
        return f"{name} hiện captcha (xác minh không phải robot)"
    return None


def check_page(platform, page):
    """Gọi trong lúc quét: thấy dấu hiệu bị nghi ngờ thì ném CheckpointError để dừng ngay."""
    try:
        title = page.title()
        has_captcha = page.locator(CAPTCHA_SELECTOR).count() > 0
    except Exception:
        title, has_captcha = "", False
    reason = detect(platform, page.url, title, has_captcha)
    if reason:
        raise CheckpointError(platform, reason, page.url)


# ---------------- trạng thái + giới hạn ----------------

def limits():
    saved = db.get_setting("safety_limits", {})
    return {p: {**DEFAULT_LIMITS[p], **saved.get(p, {})} for p in PLATFORMS}


def set_limits(platform, min_gap_s, max_per_day):
    if platform not in PLATFORMS:
        raise ValueError("Nền tảng không hợp lệ")
    if not (30 <= min_gap_s <= 3600 and 1 <= max_per_day <= 500):
        raise ValueError("Nghỉ giữa 2 lần quét: 30–3600 giây; số lần quét/ngày: 1–500")
    saved = db.get_setting("safety_limits", {})
    saved[platform] = {"min_gap_s": int(min_gap_s), "max_per_day": int(max_per_day)}
    db.set_setting("safety_limits", saved)


def blocked():
    return db.get_setting("blocked", {})


def block(platform, reason, url=None):
    b = blocked()
    b[platform] = {"reason": reason, "url": url, "ts": int(time.time())}
    db.set_setting("blocked", b)


def resume(platform):
    b = blocked()
    b.pop(platform, None)
    db.set_setting("blocked", b)


def _midnight(now=None):
    d = datetime.fromtimestamp(now or time.time())
    return int(d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def used_today(platform, now=None):
    return db.count_rate_events(platform, _midnight(now))


def before_scan(platform, log, should_stop=lambda: False, sleep=time.sleep, now=time.time):
    """Kiểm tra trước mỗi lượt quét. Ném Skipped nếu không được quét; tự nghỉ cho đủ khoảng cách tối thiểu."""
    name = PLATFORMS[platform]
    b = blocked().get(platform)
    if b:
        raise Skipped(f"{name} đang tạm dừng vì: {b['reason']}. Xác minh xong hãy bấm 'Đã xử lý, quét tiếp'.")
    lim = limits()[platform]
    used = used_today(platform, now())
    if used >= lim["max_per_day"]:
        raise Skipped(f"Đã quét {name} {used}/{lim['max_per_day']} lần hôm nay (giới hạn an toàn). Mai quét tiếp.")
    last = db.last_rate_event(platform)
    wait = int(last + lim["min_gap_s"] - now()) if last else 0
    if wait > 0:
        log(f"Nghỉ {wait} giây trước khi quét {name} (chế độ an toàn)")
        end = now() + wait
        while now() < end:
            if should_stop():
                raise Skipped("Đã dừng")
            sleep(min(1, end - now()))
    db.add_rate_event(platform, ts=int(now()))


def status():
    lim, b = limits(), blocked()
    return [{"key": p, "name": n, "blocked": b.get(p), "used_today": used_today(p),
             "last_ts": db.last_rate_event(p), **lim[p]} for p, n in PLATFORMS.items()]
