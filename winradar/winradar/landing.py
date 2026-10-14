"""Tuổi của trang bán. Shopify công khai ngày tạo sản phẩm qua /products/<handle>.json."""
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
_PRODUCT_RE = re.compile(r"(/products/[^/?#]+)")


def _iso_ts(s):
    if not s:
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def detect_platform(html):
    h = html.lower()
    if "cdn.shopify.com" in h or "shopify.theme" in h:
        return "shopify"
    if "shoplazza" in h:
        return "shoplazza"
    if "woocommerce" in h:
        return "woocommerce"
    if "shopline" in h:
        return "shopline"
    return None


def parse_shopify_product(data):
    p = data.get("product") or {}
    variants = p.get("variants") or []
    return {
        "created_ts": _iso_ts(p.get("created_at")),
        "published_ts": _iso_ts(p.get("published_at")),
        "title": p.get("title"),
        "price": variants[0].get("price") if variants else None,
    }


def check(url, client=None):
    info = {"url": url, "final_url": None, "domain": None, "platform": None, "created_ts": None,
            "published_ts": None, "title": None, "price": None, "checked_ts": int(time.time()), "error": None}
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20)
    try:
        r = client.get(url)
        final = str(r.url)
        info["final_url"] = final
        p = urlparse(final)
        info["domain"] = p.netloc.lower().removeprefix("www.")
        info["platform"] = detect_platform(r.text)
        m = _PRODUCT_RE.search(p.path)
        if m:
            j = client.get(f"{p.scheme}://{p.netloc}{m.group(1)}.json")
            if j.status_code == 200 and "application/json" in j.headers.get("content-type", ""):
                info.update(parse_shopify_product(j.json()))
                info["platform"] = "shopify"
        if not info["title"]:
            t = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
            info["title"] = t.group(1).strip()[:200] if t else None
    except Exception as e:  # mạng lỗi, shop chặn bot... ghi lại rồi bỏ qua
        info["error"] = str(e)[:300]
    finally:
        if own:
            client.close()
    return info
