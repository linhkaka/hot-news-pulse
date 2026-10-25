"""Tải ảnh / video của QC và video viral.

Link video Facebook (fbcdn) và TikTok có hạn dùng: tham số `oe=` trong link Facebook là thời điểm hết hạn
(số giây, hệ 16). Link đã hết hạn thì phải quét lại / đào sâu để lấy link mới; ảnh thì còn bản lưu trong máy.
"""
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from . import config
from .landing import UA

_EXT = {"video/mp4": ".mp4", "video/webm": ".webm", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "image/gif": ".gif"}


def link_expiry(url):
    """Thời điểm hết hạn (unix) đọc từ link fbcdn `oe=<hex>`, không có thì None."""
    try:
        oe = parse_qs(urlparse(url or "").query).get("oe")
        return int(oe[0], 16) if oe else None
    except ValueError:
        return None


def expired(url, now=None):
    exp = link_expiry(url)
    return bool(exp and exp < (now or time.time()))


def slug(text, n=50):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:n].strip("-") or "media"


def _referer(url):
    host = urlparse(url).netloc
    if "tiktok" in host:
        return "https://www.tiktok.com/"
    if "fbcdn" in host or "facebook" in host:
        return "https://www.facebook.com/"
    return None


def fetch(url, timeout=60):
    """Tải về (bytes, content-type). Lỗi mạng / link hết hạn -> ném lỗi có lời giải thích."""
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("Không có link")
    headers = {"User-Agent": UA}
    if _referer(url):
        headers["Referer"] = _referer(url)
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
    if r.status_code in (401, 403, 404, 410):
        raise ValueError("Link đã hết hạn hoặc bị chặn — quét lại / đào sâu để lấy link mới" if expired(url) or r.status_code == 403
                         else f"Không tải được (HTTP {r.status_code})")
    r.raise_for_status()
    return r.content, r.headers.get("content-type", "").split(";")[0].strip()


def ext_for(ctype, url, kind):
    if ctype in _EXT:
        return _EXT[ctype]
    path = urlparse(url).path.lower()
    for e in (".mp4", ".webm", ".jpg", ".jpeg", ".png", ".webp"):
        if path.endswith(e):
            return ".jpg" if e == ".jpeg" else e
    return ".mp4" if kind == "video" else ".jpg"


def save(data, name, folder=None):
    """Lưu vào MEDIA_DIR/<ngày>/<tên>, không ghi đè file cùng tên. Trả về đường dẫn."""
    folder = Path(folder or config.MEDIA_DIR / datetime.now().strftime("%Y-%m-%d"))
    folder.mkdir(parents=True, exist_ok=True)
    stem, ext = Path(name).stem, Path(name).suffix
    path, n = folder / name, 1
    while path.exists():
        n += 1
        path = folder / f"{stem}-{n}{ext}"
    path.write_bytes(data)
    return path
