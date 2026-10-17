"""Đọc QC từ dữ liệu JSON mà trang Thư viện quảng cáo Facebook tải về.

Facebook đổi cấu trúc thường xuyên, nên thay vì bám theo đường dẫn cố định, ta duyệt toàn bộ
cây JSON và lấy mọi object có "ad_archive_id" + "snapshot". Cách này sống sót qua phần lớn
các lần Facebook sửa giao diện.
"""
import json
import re
from urllib.parse import parse_qs, unquote, urlparse

_SCRIPT_RE = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)


def _walk(obj):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "ad_archive_id" in cur and isinstance(cur.get("snapshot"), dict):
                yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _loads_many(text):
    """Phản hồi GraphQL có thể có tiền tố 'for (;;);' và nhiều JSON nối nhau theo dòng."""
    text = text.strip()
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]
    try:
        yield json.loads(text)
        return
    except ValueError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _text(v):
    if isinstance(v, dict):
        v = v.get("text")
    if not isinstance(v, str):
        return None
    v = v.strip()
    if not v or "{{" in v:   # QC động (DCO) chứa biến kiểu {{product.name}}
        return None
    return v


def _unwrap_link(url):
    """Link qua l.facebook.com/l.php?u=... -> link thật."""
    if not url:
        return None
    p = urlparse(url)
    if p.netloc.endswith("facebook.com") and p.path.startswith("/l.php"):
        u = parse_qs(p.query).get("u")
        if u:
            return unquote(u[0])
    return url


def clean_url(url):
    """Bỏ tham số tracking, giữ scheme+domain+path để gom các QC cùng trang bán."""
    url = _unwrap_link(url)
    if not url or not url.startswith("http"):
        return None, None
    p = urlparse(url)
    domain = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/") or ""
    return f"{p.scheme}://{p.netloc.lower()}{path}", domain


def normalize(node):
    snap = node["snapshot"]
    cards = snap.get("cards") or []
    videos = list(snap.get("videos") or []) + [c for c in cards if c.get("video_preview_image_url")]
    images = list(snap.get("images") or []) + [c for c in cards if c.get("resized_image_url")]

    video_url = thumb_url = None
    if videos:
        v = videos[0]
        video_url = v.get("video_hd_url") or v.get("video_sd_url")
        thumb_url = v.get("video_preview_image_url")
    elif images:
        i = images[0]
        thumb_url = i.get("resized_image_url") or i.get("original_image_url")

    link = snap.get("link_url") or next((c.get("link_url") for c in cards if c.get("link_url")), None)
    link_url, domain = clean_url(link)
    title = _text(snap.get("title")) or next((_text(c.get("title")) for c in cards if _text(c.get("title"))), None)
    body = _text(snap.get("body")) or next((_text(c.get("body")) for c in cards if _text(c.get("body"))), None)

    return {
        "ad_id": str(node["ad_archive_id"]),
        "collation_id": str(node["collation_id"]) if node.get("collation_id") else None,
        "collation_count": int(node.get("collation_count") or 1),
        "page_id": str(node.get("page_id") or snap.get("page_id") or ""),
        "page_name": node.get("page_name") or snap.get("page_name"),
        "start_ts": node.get("start_date"),
        "end_ts": node.get("end_date"),
        "is_active": 1 if node.get("is_active") else 0,
        "title": title,
        "body": body,
        "link_url": link_url,
        "domain": domain,
        "thumb_url": thumb_url,
        "video_url": video_url,
        "has_video": bool(videos),
    }


def parse_json_text(text):
    ads = {}
    for blob in _loads_many(text):
        for node in _walk(blob):
            ad = normalize(node)
            ads[ad["ad_id"]] = ad
    return list(ads.values())


def parse_html(html):
    ads = {}
    for m in _SCRIPT_RE.finditer(html):
        chunk = m.group(1)
        if "ad_archive_id" not in chunk:
            continue
        for ad in parse_json_text(chunk):
            ads[ad["ad_id"]] = ad
    return list(ads.values())
