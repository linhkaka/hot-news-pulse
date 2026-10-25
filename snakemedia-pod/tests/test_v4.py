"""Nâng cấp 4: Kết nối Shopify + Clone sản phẩm, gợi ý từ khoá Pinterest / Google Trends, bảng tiến độ quét."""
import importlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pytest
from fastapi.testclient import TestClient

from snakepod import kwtrends, shopify
from tests.test_e2e import _chromium

NOW = 1_760_000_000

SRC_PRODUCT = {"product": {
    "title": "Personalized Dog Mom Shirt", "body_html": '<p onclick="x()">Soft tee</p><script>alert(1)</script><iframe src="//x"></iframe>',
    "vendor": "PawShop", "product_type": "T-Shirt", "tags": "dog, mom",
    "options": [{"name": "Size", "values": ["S", "M"]}, {"name": "Color", "values": ["Black", "White"]}],
    "variants": [{"option1": "S", "option2": "Black", "price": "24.99", "compare_at_price": "39.99"},
                 {"option1": "M", "option2": "Black", "price": "24.99", "compare_at_price": None},
                 {"option1": "M", "option2": "Black", "price": "26.00"}],                 # trùng -> bỏ
    "images": [{"src": "//cdn.shopify.com/a.jpg"}, {"src": "https://cdn.shopify.com/b.jpg"}]}}
OG_PAGE = """<html><head><title>Nurse Mug | Shop</title>
<meta property="og:title" content="Nurse Life Mug &amp; Gift"><meta property="og:description" content="11oz ceramic">
<meta property="og:image" content="https://img.example/m1.jpg"><meta property="og:image" content="//img.example/m2.jpg">
<meta property="product:price:amount" content="17.5"></head><body></body></html>"""


def test_source_parsers_and_product_input():
    src = shopify.from_shopify_json(SRC_PRODUCT["product"], "https://s.com/products/dog")
    assert src["images"] == ["https://cdn.shopify.com/a.jpg", "https://cdn.shopify.com/b.jpg"]
    assert "<script" not in src["body_html"] and "<iframe" not in src["body_html"] and "onclick" not in src["body_html"]
    inp = shopify.product_input(src)
    assert inp["status"] == "DRAFT" and inp["tags"] == ["dog", "mom", "snakemedia-clone"] and inp["vendor"] == "PawShop"
    assert [o["name"] for o in inp["productOptions"]] == ["Size", "Color"]
    assert [v["name"] for v in inp["productOptions"][1]["values"]] == ["Black"]          # White không có biến thể -> bỏ
    assert inp["variants"] == [
        {"optionValues": [{"optionName": "Size", "name": "S"}, {"optionName": "Color", "name": "Black"}], "price": "24.99", "compareAtPrice": "39.99"},
        {"optionValues": [{"optionName": "Size", "name": "M"}, {"optionName": "Color", "name": "Black"}], "price": "24.99"}]
    assert inp["files"][0] == {"originalSource": "https://cdn.shopify.com/a.jpg", "contentType": "IMAGE", "alt": "Personalized Dog Mom Shirt"}
    og = shopify.from_html(OG_PAGE, "https://x.com/item/1")
    assert og["title"] == "Nurse Life Mug & Gift" and og["images"] == ["https://img.example/m1.jpg", "https://img.example/m2.jpg"]
    inp = shopify.product_input(og)
    assert inp["productOptions"] == [{"name": "Title", "position": 1, "values": [{"name": "Default Title"}]}]
    assert inp["variants"] == [{"optionValues": [{"optionName": "Title", "name": "Default Title"}], "price": "17.50"}]
    assert shopify.admin_url("ten-store.myshopify.com", "gid://shopify/Product/42") == "https://admin.shopify.com/store/ten-store/products/42"


def test_shop_domain_rules(monkeypatch):
    monkeypatch.setattr(shopify.config, "SHOPIFY_BASE", None)
    assert shopify.shop_domain("https://Ten-Store.myshopify.com/admin") == "ten-store.myshopify.com"
    assert shopify.shop_domain("ten-store") == "ten-store.myshopify.com"
    with pytest.raises(shopify.ShopifyError):
        shopify.shop_domain("myshop.com")


def test_kw_parsers():
    rss = """<rss><channel><item><title>Halloween Costumes</title><ht:approx_traffic>200K+</ht:approx_traffic>
      <ht:news_item><ht:news_item_title><![CDATA[Best &amp; scariest]]></ht:news_item_title></ht:news_item></item>
      <item><title>dog bed</title><ht:approx_traffic>2,000+</ht:approx_traffic></item></channel></rss>"""
    g = kwtrends.parse_google_rss(rss)
    assert [(x["term"], x["score"]) for x in g] == [("halloween costumes", 200000), ("dog bed", 2000)]
    assert g[0]["info"] == "200K+ lượt tìm · Best & scariest"
    p = kwtrends.parse_pinterest_text(json.dumps({"data": [{"category": "Home decor", "trends": [
        {"term": "Fireplace Decor", "pct_growth_wow": 0.46}, {"term": "boots", "pct_growth_mom": 56}, {"term": "x"}]}]}))
    assert [(x["term"], x["growth"], x["group"]) for x in kwtrends.merge(p)] == [("boots", 56, "Home decor"), ("fireplace decor", 46, "Home decor")]


@pytest.fixture
def fake_shopify():
    state = {"inputs": [], "tokens": 0, "auth": []}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            body = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/products/dog-shirt":
                return self._send(200, "<html>shop</html>", "text/html")
            if self.path == "/products/dog-shirt.json":
                return self._send(200, json.dumps(SRC_PRODUCT))
            if self.path == "/item/mug":
                return self._send(200, OG_PAGE, "text/html")
            self._send(404, "{}")

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
            if self.path == "/admin/oauth/access_token":
                q = parse_qs(raw)
                if q.get("client_secret") != ["good-secret"] or q.get("grant_type") != ["client_credentials"]:
                    return self._send(401, '{"error":"invalid_client"}')
                state["tokens"] += 1
                return self._send(200, json.dumps({"access_token": f"tok{state['tokens']}", "scope": "write_products", "expires_in": 86399}))
            if self.path.startswith("/admin/api/") and self.path.endswith("/graphql.json"):
                tok = self.headers.get("X-Shopify-Access-Token")
                state["auth"].append(tok)
                if not tok or not (tok.startswith("tok") or tok == "shpat_abc"):
                    return self._send(401, "{}")
                body = json.loads(raw)
                if "shop {" in body["query"]:
                    return self._send(200, json.dumps({"data": {"shop": {"name": "Paw Store", "myshopifyDomain": "x", "currencyCode": "USD"}}}))
                state["inputs"].append(body["variables"])
                n = len(state["inputs"])
                return self._send(200, json.dumps({"data": {"productSet": {"product": {"id": f"gid://shopify/Product/{900 + n}",
                    "handle": "h", "title": body["variables"]["input"]["title"]}, "userErrors": []}}}))
            self._send(404, "{}")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.state = state
    srv.base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import analyze, db, demo, jobs, kwtrends as kw, server, shopify as sh
    for m in (db, analyze, jobs, kw, sh, demo, server):
        importlib.reload(m)
    return tmp_path


def _ad(i, link, keyword=None):
    return {"ad_id": i, "collation_id": None, "collation_count": 1, "page_id": "p" + i, "page_name": "P", "start_ts": NOW,
            "end_ts": None, "is_active": 1, "title": None, "body": "Dog mom shirt", "link_url": link,
            "domain": link.split("/")[2], "thumb_url": None, "video_url": None}


def test_connect_and_clone(app_env, monkeypatch, fake_shopify):
    from snakepod import config, db, jobs, server
    monkeypatch.setattr(config, "SHOPIFY_BASE", fake_shopify.base)
    db.init()
    db.upsert_ads([_ad("1", f"{fake_shopify.base}/products/dog-shirt"), _ad("2", f"{fake_shopify.base}/item/mug")], "dog mom shirt")
    db.set_thumb("1", None, "aaaaaaaaaaaaaaaa")
    db.set_thumb("2", None, "5555555555555555")
    jobs.recompute()
    cids = {v["ads"][0]["ad_id"]: v["cid"] for v in db.list_videos()}
    with TestClient(server.app) as c:
        assert c.get("/api/shopify").json()["connected"] is False
        r = c.post("/api/shopify/clone", json={"cid": cids["1"]})
        assert r.status_code == 400 and "Chưa kết nối" in r.json()["detail"]
        r = c.post("/api/shopify", json={"shop": "paw", "client_id": "cid1", "client_secret": "bad"})
        assert r.status_code == 400 and "từ chối" in r.json()["detail"]
        r = c.post("/api/shopify", json={"shop": "paw", "client_id": "cid1", "client_secret": "good-secret"}).json()
        assert r["connected"] and r["name"] == "Paw Store" and r["shop"] == "paw.myshopify.com"
        assert "good-secret" not in json.dumps(c.get("/api/shopify").json())                   # secret không lộ ra giao diện
        # để trống secret = giữ secret cũ
        assert c.post("/api/shopify", json={"shop": "paw.myshopify.com", "client_id": "cid1"}).json()["connected"]

        t0 = fake_shopify.state["tokens"]
        r = c.post("/api/shopify/clone", json={"cid": cids["1"]}).json()
        assert r["admin_url"] == "https://admin.shopify.com/store/paw/products/901" and r["variants"] == 2 and r["images"] == 2
        inp = fake_shopify.state["inputs"][0]
        assert inp["synchronous"] is True and inp["input"]["status"] == "DRAFT" and inp["input"]["title"] == "Personalized Dog Mom Shirt"
        assert fake_shopify.state["tokens"] == t0                                             # mã truy cập dùng lại, không xin mới mỗi lần
        r = c.post("/api/shopify/clone", json={"cid": cids["2"], "url": f"{fake_shopify.base}/item/mug"}).json()
        assert r["title"] == "Nurse Life Mug & Gift" and r["images"] == 2
        listed = {v["cid"]: v for v in c.get("/api/videos").json()["items"]}
        assert listed[cids["1"]]["clone"]["product_id"] == "gid://shopify/Product/901"
        d = c.get(f"/api/videos/{cids['1']}").json()
        assert d["clone_url"].endswith("/products/dog-shirt") and d["clone"]["shop"] == "paw.myshopify.com"
        assert c.post("/api/shopify/clone", json={"url": "ftp://x"}).status_code == 400
        # token hết hạn -> tự xin mã mới
        s = db.get_setting("shopify")
        db.set_setting("shopify", {**s, "token_exp": 1})
        c.post("/api/shopify/clone", json={"url": f"{fake_shopify.base}/item/mug"})
        assert fake_shopify.state["tokens"] == t0 + 1 and fake_shopify.state["auth"][-1] == f"tok{t0 + 1}"
        # Admin API access token dán thẳng (custom app cũ)
        c.delete("/api/shopify")
        assert c.post("/api/shopify", json={"shop": "paw", "client_secret": "shpat_abc"}).json()["connected"]
        assert c.post("/api/shopify/clone", json={"url": f"{fake_shopify.base}/item/mug"}).status_code == 200
        assert fake_shopify.state["auth"][-1] == "shpat_abc"
        assert c.get("/api/shopify").json()["clones"] == 2


def test_kwtrends_google_and_scanned_flags(app_env, monkeypatch):
    from snakepod import config, db, jobs, server

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = (f"<rss><channel><item><title>Dog Mom Shirt</title><ht:approx_traffic>5K+</ht:approx_traffic></item>"
                    f"<item><title>nba finals</title><ht:approx_traffic>500K+</ht:approx_traffic></item><geo>{self.path}</geo></channel></rss>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(config, "GOOGLE_TRENDS_RSS", f"http://127.0.0.1:{srv.server_address[1]}/rss?geo={{geo}}")
    db.init()
    db.add_watch_keyword("dog mom shirt", "GB")
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda kind, title, fn: queued.append((title, fn)) or True)
    try:
        with TestClient(server.app) as c:
            assert c.post("/api/kwtrends/refresh", json={"source": "x"}).status_code == 400
            assert c.post("/api/kwtrends/refresh", json={"source": "google", "countries": ["gb", "GB", "us"]}).json()["queued"] == 2
            assert [t for t, _ in queued] == ["Xu hướng Google Trends GB", "Xu hướng Google Trends US"]
            assert queued[0][1]() == 2
            r = c.get("/api/kwtrends", params={"source": "google", "market": "gb"}).json()
            assert [(x["term"], x["scanned"]) for x in r["items"]] == [("nba finals", False), ("dog mom shirt", True)]
            assert r["unscanned"] == 1 and r["markets"] == ["GB"] and r["ts"]
            assert c.get("/api/kwtrends", params={"source": "google", "market": "US"}).json()["items"] == []
    finally:
        srv.shutdown()


def test_progress_panel_math(app_env, monkeypatch):
    from snakepod import jobs
    jobs.SESSION.clear()
    jobs.SESSION.extend([{"title": "Quét 'a'", "kind": "keyword", "n": 120, "status": "xong", "secs": 60, "ts": NOW},
                         {"title": "Quét 'b'", "kind": "keyword", "n": 0, "status": "loi", "secs": 20, "ts": NOW}])
    monkeypatch.setitem(jobs._state, "current", "Quét 'c'")
    monkeypatch.setitem(jobs._state, "kind", "keyword")
    monkeypatch.setitem(jobs._state, "started", NOW - 40)
    monkeypatch.setitem(jobs._state, "count", 80)
    monkeypatch.setitem(jobs._state, "pending", ["Quét 'd'", "Quét 'e'"])
    p = jobs.progress(now=NOW)
    assert p["total"] == 5 and p["n_done"] == 2 and p["current"] == {"title": "Quét 'c'", "kind": "keyword", "count": 80, "secs": 40}
    assert p["items"] == 200 and p["rate"] == 100                     # 200 QC / 120 giây
    assert p["eta_s"] == 2 * 40 + 0                                    # trung bình 40 giây/việc, việc đang chạy đã quá trung bình
    monkeypatch.setitem(jobs._state, "pending", [])
    monkeypatch.setitem(jobs._state, "current", None)
    assert jobs.progress(now=NOW)["eta_s"] == 0
    jobs.SESSION.clear()


def test_queue_records_session(app_env):
    from snakepod import db, jobs
    db.init()
    jobs.SESSION.clear()
    jobs.start_worker()

    def work():
        jobs.set_progress(7)
        time.sleep(0.2)
        return 7
    jobs.submit("keyword", "Quét 'p1'", work)
    jobs.submit("keyword", "Quét 'p2'", lambda: (_ for _ in ()).throw(RuntimeError("hỏng")))
    for _ in range(50):
        if len(jobs.SESSION) == 2:
            break
        time.sleep(0.1)
    p = jobs.status()["progress"]
    assert [(d["title"], d["n"], d["status"]) for d in p["done"]] == [("Quét 'p1'", 7, "xong"), ("Quét 'p2'", 0, "loi")]
    jobs.submit("keyword", "Quét 'p3'", lambda: 1)                       # hàng đợi rảnh -> phiên mới
    for _ in range(50):
        if jobs.SESSION and jobs.SESSION[-1]["title"] == "Quét 'p3'":
            break
        time.sleep(0.1)
    assert [d["title"] for d in jobs.SESSION] == ["Quét 'p3'"]


@pytest.mark.skipif(_chromium() is None, reason="không có Chromium")
def test_pinterest_trends_scan_with_browser(app_env, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_HEADLESS", "1")
    monkeypatch.setenv("SNAKEPOD_SCROLL_MS", "300,600")
    if _chromium():
        monkeypatch.setenv("SNAKEPOD_CHROMIUM", _chromium())
    monkeypatch.delenv("SNAKEPOD_PROXY", raising=False)
    from snakepod import config
    importlib.reload(config)
    monkeypatch.setattr(config, "PROXY_FILE", app_env / "proxy.txt")
    from snakepod import db, jobs, safety, scraper
    for m in (db, scraper, jobs):
        importlib.reload(m)
    monkeypatch.setitem(safety.DEFAULT_LIMITS, "pinterest", {"min_gap_s": 0, "max_per_day": 100})
    paths = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype):
            body = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            paths.append(self.path)
            if self.path.startswith("/trends-home"):
                self._send("""<html><body style="height:3000px">
<script type="application/json">{"seed":[{"term":"Halloween Decor","pct_growth_wow":1.2}]}</script>
<script>fetch('/resource/TrendsResource/get?x=1');</script></body></html>""", "text/html")
            elif self.path.startswith("/resource/"):
                self._send(json.dumps({"resource_response": {"data": [{"category_name": "Shoes", "items": [
                    {"term": "Boots", "pct_growth_mom": 0.56}, {"term": "slippers", "pct_growth_mom": 0.54}]}]}}), "application/json")
            else:
                self._send("{}", "application/json")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(config, "PINTEREST_TRENDS", f"http://127.0.0.1:{srv.server_address[1]}/trends-home?country={{geo}}")
    try:
        db.init()
        assert jobs.kwtrend_job("pinterest", "GB")() == 3
        assert any("country=GB" in p for p in paths)
        items = db.get_setting("kwtrends")["pinterest"]["GB"]["items"]
        assert [(x["term"], x["growth"], x["group"]) for x in items] == [("halloween decor", 120, None), ("boots", 56, "Shoes"),
                                                                         ("slippers", 54, "Shoes")]
    finally:
        srv.shutdown()
