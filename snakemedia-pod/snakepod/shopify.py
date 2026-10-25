"""Kết nối Shopify + Clone sản phẩm vào store của bạn.

Kết nối: app tự tạo trong Shopify Dev Dashboard (Client ID + Client secret, cài vào store của bạn) -> lấy mã truy cập
bằng "client credentials" (hết hạn sau ~24 giờ, tool tự lấy lại). Hoặc dán thẳng Admin API access token (shpat_...)
của custom app tạo trong Shopify admin.

Clone: đọc sản phẩm của trang bán (Shopify: /products/<handle>.json; nền tảng khác: thẻ og: trong trang)
rồi tạo sản phẩm NHÁP (Draft) trong store của bạn qua Admin GraphQL `productSet`. Không tự đăng bán.
"""
import html as htmllib
import re
import time
from urllib.parse import urlparse

import httpx

from . import config, db, landing

_SHOP_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")
_OG_RE = re.compile(r'<meta[^>]+(?:property|name)=["\'](og:[a-z:_]+|product:price:amount|twitter:image)["\'][^>]*>', re.I)
_CONTENT_RE = re.compile(r'content=["\']([^"\']*)["\']', re.I)
_DANGER_RE = re.compile(r"<(script|style|iframe|object|embed)[^>]*>.*?</\1\s*>|<(script|iframe|object|embed)[^>]*/?>", re.I | re.S)
_ON_RE = re.compile(r'\s+on[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', re.I)

MUTATION = """mutation productSet($input: ProductSetInput!, $synchronous: Boolean!) {
  productSet(synchronous: $synchronous, input: $input) {
    product { id handle title }
    userErrors { field message code }
  }
}"""


class ShopifyError(Exception):
    pass


def shop_domain(raw):
    """'ten-store', 'https://ten-store.myshopify.com/admin' -> 'ten-store.myshopify.com'."""
    s = (raw or "").strip().lower()
    s = re.sub(r"^https?://", "", s).split("/")[0]
    if s and "." not in s:
        s += ".myshopify.com"
    if config.SHOPIFY_BASE:                       # kiểm thử: chấp nhận mọi tên
        return s
    if not _SHOP_RE.match(s):
        raise ShopifyError("Tên store phải có dạng ten-store.myshopify.com (xem ở Shopify admin → Settings → Domains)")
    return s


def _base(shop):
    return config.SHOPIFY_BASE or f"https://{shop}"


def settings():
    return db.get_setting("shopify", {})


def status():
    s = settings()
    secret = s.get("secret") or ""
    return {"connected": bool(s.get("name")), "shop": s.get("shop"), "name": s.get("name"), "currency": s.get("currency"),
            "client_id": s.get("client_id"), "secret_masked": (secret[:4] + "…" + secret[-4:]) if len(secret) > 10 else bool(secret),
            "scopes": config.SHOPIFY_SCOPES, "clones": len(db.get_setting("clones", {}))}


def _token(s, client):
    secret = s.get("secret") or ""
    if secret.startswith("shpat_"):               # Admin API access token dán thẳng
        return secret
    if s.get("token") and (s.get("token_exp") or 0) > time.time() + 300:
        return s["token"]
    if not s.get("client_id"):
        raise ShopifyError("Thiếu Client ID")
    r = client.post(f"{_base(s['shop'])}/admin/oauth/access_token",
                    data={"grant_type": "client_credentials", "client_id": s["client_id"], "client_secret": secret})
    if r.status_code != 200:
        raise ShopifyError(f"Shopify từ chối Client ID / Client secret (mã {r.status_code}). Kiểm tra app đã được "
                           "cài (Install app) vào đúng store này chưa.")
    j = r.json()
    s["token"], s["token_exp"] = j["access_token"], int(time.time()) + int(j.get("expires_in") or 86399)
    if s.get("name"):                             # đã kết nối: lưu mã mới (chỉ khi vẫn đang nối đúng store này)
        db.update_setting("shopify", lambda cur: {**cur, "token": s["token"], "token_exp": s["token_exp"]}
                          if (cur or {}).get("shop") == s["shop"] and cur.get("name") else cur, {})
    return s["token"]


def gql(s, query, variables=None, client=None):
    own = client is None
    client = client or httpx.Client(timeout=60)
    try:
        token = _token(s, client)
        r = client.post(f"{_base(s['shop'])}/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json",
                        json={"query": query, "variables": variables or {}},
                        headers={"X-Shopify-Access-Token": token})
        if r.status_code in (401, 403):
            raise ShopifyError("Mã truy cập không hợp lệ hoặc thiếu quyền write_products. Kết nối lại.")
        r.raise_for_status()
        j = r.json()
        if j.get("errors"):
            raise ShopifyError("Shopify báo lỗi: " + "; ".join(str(e.get("message", e)) for e in j["errors"])[:300])
        return j["data"]
    except httpx.HTTPError as e:
        raise ShopifyError(f"Không gọi được Shopify: {e}") from e
    finally:
        if own:
            client.close()


def connect(shop, client_id, secret):
    shop = shop_domain(shop)
    old = settings()
    if not secret and old.get("shop") == shop:   # để trống = giữ secret cũ
        secret = old.get("secret")
    if not secret:
        raise ShopifyError("Nhập Client secret (hoặc Admin API access token shpat_...)")
    s = {"shop": shop, "client_id": (client_id or "").strip(), "secret": secret.strip()}
    data = gql(s, "{ shop { name myshopifyDomain currencyCode } }")
    s.update(name=data["shop"]["name"], currency=data["shop"].get("currencyCode"))
    db.set_setting("shopify", s)
    return status()


def disconnect():
    db.set_setting("shopify", {})


# ---------------- đọc sản phẩm nguồn ----------------

def clean_html(h):
    h = _DANGER_RE.sub("", h or "")
    return _ON_RE.sub("", h)


def _money(v):
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return f"{x:.2f}" if x >= 0 else None


def from_shopify_json(p, url):
    """Sản phẩm từ /products/<handle>.json của Shopify."""
    opts = [{"name": o.get("name") or f"Option {i + 1}", "values": list(dict.fromkeys(o.get("values") or []))}
            for i, o in enumerate(p.get("options") or [])]
    variants = []
    for v in (p.get("variants") or [])[: config.CLONE_MAX_VARIANTS]:
        vals = [v.get(f"option{i + 1}") for i in range(len(opts))]
        variants.append({"options": vals, "price": _money(v.get("price")) or "0.00",
                         "compare_at_price": _money(v.get("compare_at_price"))})
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    imgs = [i.get("src") for i in p.get("images") or [] if i.get("src")]
    return {"title": p.get("title") or "Sản phẩm", "body_html": clean_html(p.get("body_html")), "vendor": p.get("vendor"),
            "product_type": p.get("product_type"), "tags": tags, "options": opts, "variants": variants,
            "images": [("https:" + u) if u.startswith("//") else u for u in imgs][: config.CLONE_MAX_IMAGES], "source_url": url}


def from_html(page, url):
    """Nền tảng khác: đọc thẻ og:title / og:description / og:image / giá trong trang."""
    meta = {}
    images = []
    for m in _OG_RE.finditer(page):
        c = _CONTENT_RE.search(m.group(0))
        if not c:
            continue
        k, val = m.group(1).lower(), htmllib.unescape(c.group(1)).strip()
        if k in ("og:image", "og:image:secure_url", "twitter:image"):
            images.append(("https:" + val) if val.startswith("//") else val)
        else:
            meta.setdefault(k, val)
    t = landing.TITLE_RE.search(page)
    title = meta.get("og:title") or (htmllib.unescape(t.group(1)).strip() if t else None) or "Sản phẩm"
    price = _money(meta.get("product:price:amount") or meta.get("og:price:amount")) or _money(landing._price_from_html(page)) or "0.00"
    desc = meta.get("og:description")
    return {"title": title[:255], "body_html": f"<p>{htmllib.escape(desc)}</p>" if desc else "", "vendor": None,
            "product_type": None, "tags": [], "options": [], "variants": [{"options": [], "price": price, "compare_at_price": None}],
            "images": list(dict.fromkeys(u for u in images if u.startswith("http")))[: config.CLONE_MAX_IMAGES], "source_url": url}


def source_product(url, client=None):
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": landing.UA}, follow_redirects=True, timeout=30)
    try:
        r = client.get(url)
        r.raise_for_status()
        final = urlparse(str(r.url))
        m = re.search(r"/products/([^/?#]+)", final.path)
        if m:
            try:
                j = client.get(f"{final.scheme}://{final.netloc}/products/{m.group(1)}.json")
                if j.status_code == 200 and "json" in j.headers.get("content-type", ""):
                    return from_shopify_json(j.json().get("product") or {}, url)
            except (httpx.HTTPError, ValueError):
                pass
        return from_html(r.text, url)
    except httpx.HTTPError as e:
        raise ShopifyError(f"Không đọc được trang bán: {e}") from e
    finally:
        if own:
            client.close()


def product_input(src):
    """Dữ liệu sản phẩm -> ProductSetInput (luôn ở trạng thái DRAFT)."""
    opts = [o for o in src["options"] if o["values"]]
    variants = src["variants"] or [{"options": [], "price": "0.00", "compare_at_price": None}]
    if not opts:                                   # sản phẩm 1 biến thể: Shopify vẫn cần 1 tuỳ chọn "Title"
        opts = [{"name": "Title", "values": ["Default Title"]}]
        variants = [{**variants[0], "options": ["Default Title"]}]
    out_vars, seen = [], set()
    for v in variants:
        vals = [(x or opts[i]["values"][0]) for i, x in enumerate((v["options"] + [None] * len(opts))[: len(opts)])]
        if tuple(vals) in seen:
            continue
        seen.add(tuple(vals))
        item = {"optionValues": [{"optionName": o["name"], "name": vals[i]} for i, o in enumerate(opts)], "price": v["price"]}
        if v.get("compare_at_price") and float(v["compare_at_price"]) > float(v["price"]):
            item["compareAtPrice"] = v["compare_at_price"]
        out_vars.append(item)
    used = {o["name"]: {ov["name"] for v in out_vars for ov in v["optionValues"] if ov["optionName"] == o["name"]} for o in opts}
    inp = {"title": src["title"][:255], "descriptionHtml": src["body_html"] or "", "status": "DRAFT",
           "tags": list(dict.fromkeys([*src["tags"][:40], "snakemedia-clone"])),
           "productOptions": [{"name": o["name"], "position": i + 1,
                               "values": [{"name": x} for x in o["values"] if x in used[o["name"]]]}
                              for i, o in enumerate(opts)],
           "variants": out_vars,
           "files": [{"originalSource": u, "contentType": "IMAGE", "alt": src["title"][:255]} for u in src["images"]]}
    if src.get("vendor"):
        inp["vendor"] = src["vendor"][:255]
    if src.get("product_type"):
        inp["productType"] = src["product_type"][:255]
    return inp


def admin_url(shop, gid):
    return f"https://admin.shopify.com/store/{shop.split('.')[0]}/products/{gid.rsplit('/', 1)[-1]}"


def clone(url, cid=None):
    s = settings()
    if not s.get("name"):
        raise ShopifyError("Chưa kết nối Shopify (Cài đặt → Kết nối Shopify)")
    src = source_product(url)
    inp = product_input(src)
    data = gql(s, MUTATION, {"input": inp, "synchronous": True})
    res = data["productSet"]
    if res.get("userErrors"):
        raise ShopifyError("Shopify không nhận sản phẩm: " + "; ".join(e["message"] for e in res["userErrors"])[:400])
    p = res["product"]
    rec = {"url": url, "product_id": p["id"], "title": p.get("title") or src["title"], "admin_url": admin_url(s["shop"], p["id"]),
           "shop": s["shop"], "ts": int(time.time()), "images": len(src["images"]), "variants": len(inp["variants"])}
    if cid:
        db.update_setting("clones", lambda c: {**(c or {}), cid: rec}, {})
    return rec
