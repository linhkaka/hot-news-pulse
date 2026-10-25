"""Tuổi của trang bán.

Thứ tự tin cậy (lấy nguồn đáng tin nhất tìm được):
  1. "api"   - Shopify /products/<handle>.json, hoặc JSON sản phẩm nhúng trong trang có created_at
  2. "uuid"  - mã sản phẩm dạng UUID phiên bản 1 (chứa sẵn thời điểm tạo) - hay gặp ở nền tảng Trung Quốc
  3. "anh"   - mốc thời gian trong link ảnh sản phẩm (Shopify ?v=<unix>, /uploads/YYYY/MM/ ...)
Nguồn 2-3 là ƯỚC TÍNH, giao diện sẽ ghi rõ.
"""
import json
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .pod import detect_pod_markers

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
_PRODUCT_RE = re.compile(r"(/products?/[^/?#]+)")
_DATE_KEYS = r'"(?:created_at|createdAt|create_time|created_time|published_at|publishedAt|datePublished|release_date)"'
_DATE_RE = re.compile(_DATE_KEYS + r'\s*:\s*"?([0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+(?:Z|[+-][0-9:]{4,5})?|[0-9]{10,13})"?')
_UUID_RE = re.compile(r'"(?:product_id|productId|id|spu_id)"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-1[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12})"', re.I)
_IMG_V_RE = re.compile(r'(?:cdn\.shopify\.com|/cdn/shop)/[^"\'\s]+?\?v=(1[5-9][0-9]{8})')
_UPLOADS_RE = re.compile(r'/uploads/(20[1-3][0-9])/(0[1-9]|1[0-2])/')
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_MIN_TS = 1262304000   # 2010-01-01: bỏ mốc vô lý


def _iso_ts(s):
    if not s:
        return None
    s = str(s).strip()
    if s.isdigit():
        v = int(s[:10])
        return v if v > _MIN_TS else None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    v = int(dt.timestamp())
    return v if v > _MIN_TS else None


def uuid1_ts(value):
    """Thời điểm tạo nằm sẵn trong UUID phiên bản 1."""
    try:
        u = uuid.UUID(value)
    except ValueError:
        return None
    if u.version != 1:
        return None
    ts = (u.time - 0x01B21DD213814000) / 1e7
    return int(ts) if _MIN_TS < ts < time.time() + 86400 else None


def detect_platform(html):
    h = html.lower()
    if "cdn.shopify.com" in h or "shopify.theme" in h:
        return "shopify"
    if "shoplazza" in h or "staticdj.com" in h:
        return "shoplazza"
    if "shopline" in h:
        return "shopline"
    if "woocommerce" in h:
        return "woocommerce"
    pods = detect_pod_markers(html)
    for name in ("shopbase", "gearlaunch", "teechip"):
        if name in pods:
            return name
    return None


def parse_shopify_product(data):
    p = data.get("product") or {}
    variants = p.get("variants") or []
    return {
        "created_ts": _iso_ts(p.get("created_at")),
        "published_ts": _iso_ts(p.get("published_at")),
        "title": p.get("title"),
        "price": variants[0].get("price") if variants else None,
        "compare_price": (variants[0].get("compare_at_price") or None) if variants else None,
    }


def dates_from_html(html):
    """Tìm ngày tạo sản phẩm trong trang. Trả về (ts, nguồn) hoặc (None, None)."""
    found = [t for m in _DATE_RE.finditer(html) if (t := _iso_ts(m.group(1)))]
    if found:
        return min(found), "api"
    ids = [t for m in _UUID_RE.finditer(html) if (t := uuid1_ts(m.group(1)))]
    if ids:
        return min(ids), "uuid"
    imgs = [int(v) for v in _IMG_V_RE.findall(html)]
    ups = [int(datetime(int(y), int(mo), 1, tzinfo=timezone.utc).timestamp()) for y, mo in _UPLOADS_RE.findall(html)]
    stamps = [t for t in imgs + ups if t > _MIN_TS]
    if stamps:
        return min(stamps), "anh"
    return None, None


def _price_from_html(html):
    m = re.search(r'"price"\s*:\s*"?([0-9]+(?:\.[0-9]{1,2})?)"?', html)
    return m.group(1) if m else None


def check(url, client=None):
    info = {"url": url, "final_url": None, "domain": None, "platform": None, "created_ts": None,
            "published_ts": None, "title": None, "price": None, "checked_ts": int(time.time()), "error": None,
            "date_source": None, "pod_markers": None, "compare_price": None}
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20)
    try:
        r = client.get(url)
        html = r.text
        final = str(r.url)
        info["final_url"] = final
        p = urlparse(final)
        info["domain"] = p.netloc.lower().removeprefix("www.")
        info["platform"] = detect_platform(html)
        info["pod_markers"] = ",".join(detect_pod_markers(html)) or None
        m = _PRODUCT_RE.search(p.path)
        if m and m.group(1).startswith("/products/"):
            try:
                j = client.get(f"{p.scheme}://{p.netloc}{m.group(1)}.json")
                if j.status_code == 200 and "json" in j.headers.get("content-type", ""):
                    data = parse_shopify_product(j.json())
                    if data["created_ts"]:
                        info.update(data)
                        info["platform"] = info["platform"] or "shopify"
                        info["date_source"] = "api"
            except (httpx.HTTPError, json.JSONDecodeError):
                pass
        if not info["created_ts"]:
            ts, source = dates_from_html(html)
            info["created_ts"], info["date_source"] = ts, source
        if not info["title"]:
            t = TITLE_RE.search(html)
            info["title"] = t.group(1).strip()[:200] if t else None
        if not info["price"]:
            info["price"] = _price_from_html(html)
    except Exception as e:  # mạng lỗi, shop chặn bot... ghi lại rồi bỏ qua
        info["error"] = str(e)[:300]
    finally:
        if own:
            client.close()
    return info
