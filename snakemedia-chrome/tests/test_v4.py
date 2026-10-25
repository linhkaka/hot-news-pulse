"""Nâng cấp 4 trong tiện ích: Kết nối Shopify + Clone, gợi ý từ khoá Pinterest / Google Trends, bảng tiến độ quét,
thẻ video kiểu lưới — giống hệt bản app (so khớp với code Python)."""
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pytest

from snakepod import kwtrends, shopify

SRC = {"title": "Personalized Dog Mom Shirt", "body_html": '<p onclick="x()">Soft tee</p><script>alert(1)</script><iframe src="//x"></iframe>',
       "vendor": "PawShop", "product_type": "T-Shirt", "tags": "dog, mom",
       "options": [{"name": "Size", "values": ["S", "M"]}, {"name": "Color", "values": ["Black", "White"]}],
       "variants": [{"option1": "S", "option2": "Black", "price": "24.99", "compare_at_price": "39.99"},
                    {"option1": "M", "option2": "Black", "price": "24.99", "compare_at_price": None},
                    {"option1": "M", "option2": "Black", "price": "26.00"}],
       "images": [{"src": "//cdn.shopify.com/a.jpg"}, {"src": "https://cdn.shopify.com/b.jpg"}]}
OG_PAGE = """<html><head><title>Nurse Mug | Shop</title>
<meta property="og:title" content="Nurse Life Mug &amp; Gift"><meta property="og:description" content="11oz 'ceramic' <b>">
<meta property="og:image" content="https://img.example/m1.jpg"><meta property="og:image" content="//img.example/m2.jpg">
<meta property="product:price:amount" content="17.5"></head><body></body></html>"""


def _random_product(rnd):
    opts = [{"name": n, "values": rnd.sample(["S", "M", "L", "XL", "Red", "Blue"], rnd.randint(1, 4))}
            for n in rnd.sample(["Size", "Color", "Style"], rnd.randint(0, 3))]
    variants = []
    for _ in range(rnd.randint(0, 6)):
        v = {"price": rnd.choice(["9.99", "19", "24.5", None, "0"]), "compare_at_price": rnd.choice([None, "", "29.99", "5"])}
        for i, o in enumerate(opts):
            v[f"option{i + 1}"] = rnd.choice(o["values"] + [None])
        variants.append(v)
    return {"title": rnd.choice(["Mug", "", "Dog shirt " * 40]), "body_html": rnd.choice([None, "<p>x</p>", "<style>a{}</style><b onmouseover='y'>z</b>"]),
            "vendor": rnd.choice([None, "V"]), "product_type": rnd.choice([None, "Mug"]),
            "tags": rnd.choice(["a, b", ["c", "d"], "", None]), "options": opts, "variants": variants,
            "images": [{"src": rnd.choice(["//cdn/x.jpg", "https://cdn/y.jpg"])} for _ in range(rnd.randint(0, 3))]}


def test_parsers_and_product_input_match_python(ext):
    rnd = random.Random(7)
    for p in [SRC] + [_random_product(rnd) for _ in range(40)]:
        py = shopify.from_shopify_json(p, "https://s/products/x")
        js = ext.js("p => SP.shopify.fromShopifyJson(p, 'https://s/products/x')", p)
        assert py == js
        assert shopify.product_input(py) == ext.js("s => SP.shopify.productInput(s)", py)
    py = shopify.from_html(OG_PAGE, "https://x/i")
    assert py == ext.js("h => SP.shopify.fromHtml(h, 'https://x/i')", OG_PAGE)
    assert shopify.product_input(py) == ext.js("s => SP.shopify.productInput(s)", py)
    assert ext.js("() => SP.shopify.adminUrl('ten-store.myshopify.com', 'gid://shopify/Product/42')") == \
        "https://admin.shopify.com/store/ten-store/products/42"
    rss = """<rss><channel><item><title>Halloween Costumes</title><ht:approx_traffic>200K+</ht:approx_traffic>
      <ht:news_item><ht:news_item_title><![CDATA[Best &amp; scariest]]></ht:news_item_title></ht:news_item></item>
      <item><title>dog bed</title><ht:approx_traffic>2,000+</ht:approx_traffic></item><item><title></title></item></channel></rss>"""
    assert kwtrends.parse_google_rss(rss) == ext.js("t => SP.kwtrends.parseGoogleRss(t)", rss)
    pin = json.dumps({"data": [{"category": "Home decor", "trends": [{"term": "Fireplace Decor", "pct_growth_wow": 0.465},
        {"term": "boots", "pct_growth_mom": 56}, {"term": "x"}, {"keyword": " Slippers ", "wow": -0.125}]},
        {"interest": "Pets", "list": [{"query": "dog bed", "growth_yoy": 2.5}]}]})
    py = kwtrends.parse_pinterest_text(pin)
    assert py == ext.js("t => SP.kwtrends.parsePinterestText(t)", pin)
    assert kwtrends.merge(py) == ext.js("t => SP.kwtrends.merge(SP.kwtrends.parsePinterestText(t))", pin)


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
            port = self.server.server_address[1]
            if self.path == "/products/dog-shirt":
                return self._send(200, "<html>shop</html>", "text/html")
            if self.path == "/products/dog-shirt.json":
                return self._send(200, json.dumps({"product": SRC}))
            if self.path == "/item/mug":
                return self._send(200, OG_PAGE, "text/html")
            if self.path.startswith("/rss"):
                return self._send(200, "<rss><channel><item><title>Dog Mom Shirt</title><ht:approx_traffic>5K+</ht:approx_traffic></item>"
                                       "<item><title>nba finals</title><ht:approx_traffic>500K+</ht:approx_traffic></item></channel></rss>",
                                  "application/rss+xml")
            if self.path.startswith("/trends-home"):
                state.setdefault("pin", []).append(self.path)
                return self._send(200, """<html><body style="height:3000px">
<script type="application/json">{"seed":[{"term":"Halloween Decor","pct_growth_wow":1.2}]}</script>
<script>fetch('/resource/TrendsResource/get?x=1');</script></body></html>""", "text/html")
            if self.path.startswith("/resource/"):
                return self._send(200, json.dumps({"resource_response": {"data": [{"category_name": "Shoes", "items": [
                    {"term": "Boots", "pct_growth_mom": 0.56}, {"term": "slippers", "pct_growth_mom": 0.54}]}]}}))
            self._send(404, "{}")

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
            if self.path == "/admin/oauth/access_token":
                q = parse_qs(raw)
                if q.get("client_secret") != ["good-secret"] or q.get("grant_type") != ["client_credentials"]:
                    return self._send(401, '{"error":"invalid_client"}')
                state["tokens"] += 1
                return self._send(200, json.dumps({"access_token": f"tok{state['tokens']}", "expires_in": 86399}))
            if self.path.endswith("/graphql.json"):
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


def test_connect_and_clone(ext, fake_shopify):
    base = fake_shopify.base
    ext.dev(base, urls={"SHOPIFY_BASE": base})
    ad = lambda i, link: {"ad_id": i, "collation_id": None, "collation_count": 1, "page_id": "p" + i, "page_name": "P",
                          "start_ts": 1_760_000_000, "end_ts": None, "is_active": 1, "title": None, "body": "Dog mom shirt",
                          "link_url": link, "domain": "127.0.0.1", "thumb_url": None, "video_url": None}
    ext.js("""async ([a, b]) => {
      await SP.db.upsertAds([a, b], 'dog mom shirt');
      await SP.db.setThumb('1', null, 'aaaaaaaaaaaaaaaa');
      await SP.db.setThumb('2', null, '5555555555555555');
      await SP.jobs.recompute();
    }""", [ad("1", f"{base}/products/dog-shirt"), ad("2", f"{base}/item/mug")])
    cids = {v["ads"][0]["ad_id"]: v["cid"] for v in ext.js("() => SP.db.listVideos()")}
    assert ext.get("/api/shopify")["connected"] is False
    r = ext.call("POST", "/api/shopify/clone", {"cid": cids["1"]}, ok=False)
    assert r["status"] == 400 and "Chưa kết nối" in r["detail"]
    r = ext.call("POST", "/api/shopify", {"shop": "paw", "client_id": "cid1", "client_secret": "bad"}, ok=False)
    assert r["status"] == 400 and "từ chối" in r["detail"]
    r = ext.post("/api/shopify", {"shop": "paw", "client_id": "cid1", "client_secret": "good-secret"})
    assert r["connected"] and r["name"] == "Paw Store" and r["shop"] == "paw.myshopify.com"
    assert "good-secret" not in json.dumps(ext.get("/api/shopify"))
    t0 = fake_shopify.state["tokens"]
    r = ext.post("/api/shopify/clone", {"cid": cids["1"]})
    assert r["admin_url"] == "https://admin.shopify.com/store/paw/products/901" and r["variants"] == 2 and r["images"] == 2
    expected = shopify.product_input(shopify.from_shopify_json(SRC, "x"))
    assert fake_shopify.state["inputs"][0] == {"input": expected, "synchronous": True}       # đúng như bản app gửi
    assert fake_shopify.state["tokens"] == t0
    r = ext.post("/api/shopify/clone", {"cid": cids["2"], "url": f"{base}/item/mug"})
    assert r["title"] == "Nurse Life Mug & Gift" and r["images"] == 2
    listed = {v["cid"]: v for v in ext.get("/api/videos")["items"]}
    assert listed[cids["1"]]["clone"]["product_id"] == "gid://shopify/Product/901"
    assert ext.get(f"/api/videos/{cids['1']}")["clone_url"].endswith("/products/dog-shirt")
    assert ext.call("POST", "/api/shopify/clone", {"url": "ftp://x"}, ok=False)["status"] == 400
    ext.js("async () => { const s = await SP.db.getSetting('shopify'); s.token_exp = 1; await SP.db.setSetting('shopify', s); }")
    ext.post("/api/shopify/clone", {"url": f"{base}/item/mug"})
    assert fake_shopify.state["tokens"] == t0 + 1 and fake_shopify.state["auth"][-1] == f"tok{t0 + 1}"
    ext.call("DELETE", "/api/shopify")
    assert ext.post("/api/shopify", {"shop": "paw", "client_secret": "shpat_abc"})["connected"]
    ext.post("/api/shopify/clone", {"url": f"{base}/item/mug"})
    assert fake_shopify.state["auth"][-1] == "shpat_abc" and ext.get("/api/shopify")["clones"] == 2


def test_keyword_trends_google_and_pinterest(ext, fake_shopify):
    base = fake_shopify.base
    ext.dev(base, urls={"GOOGLE_TRENDS_RSS": base + "/rss?geo={geo}", "PINTEREST_TRENDS": base + "/trends-home?country={geo}"})
    ext.js("SP.db.addWatchKeyword('dog mom shirt', 'GB')")
    assert ext.call("POST", "/api/kwtrends/refresh", {"source": "x"}, ok=False)["status"] == 400
    assert ext.post("/api/kwtrends/refresh", {"source": "google", "countries": ["gb", "GB"]})["queued"] == 1
    ext.wait_idle()
    r = ext.get("/api/kwtrends?source=google&market=gb")
    assert [(x["term"], x["scanned"]) for x in r["items"]] == [("nba finals", False), ("dog mom shirt", True)]
    assert r["unscanned"] == 1 and r["markets"] == ["GB"]
    assert ext.post("/api/kwtrends/refresh", {"source": "pinterest", "countries": ["GB"]})["queued"] == 1
    ext.wait_idle()
    assert any("country=GB" in p for p in fake_shopify.state["pin"])
    items = ext.get("/api/kwtrends?source=pinterest&market=GB")["items"]
    assert [(x["term"], x["growth"], x["group"]) for x in items] == [("halloween decor", 120, None), ("boots", 56, "Shoes"),
                                                                     ("slippers", 54, "Shoes")]
    p = ext.get("/api/jobs")["progress"]
    assert [(d["title"], d["n"], d["status"]) for d in p["done"]] == [("Xu hướng Pinterest Trends GB", 3, "xong")]


def test_progress_math_matches_app(ext):
    r = ext.js("""() => {
      const {state, SESSION} = SP.jobs._test;
      SESSION.length = 0;
      SESSION.push({title: "a", kind: "keyword", n: 120, status: "xong", secs: 60, ts: 0},
                   {title: "b", kind: "keyword", n: 0, status: "loi", secs: 20, ts: 0});
      const save = {...state, pending: state.pending};
      Object.assign(state, {current: "c", kind: "keyword", started: 1000 - 40, count: 80, pending: [{title: "d"}, {title: "e"}]});
      const p = SP.jobs.progress(1000);
      Object.assign(state, save, {current: null, pending: []});
      SESSION.length = 0;
      return p;
    }""")
    assert r["total"] == 5 and r["items"] == 200 and r["rate"] == 100 and r["eta_s"] == 80
    assert r["current"] == {"title": "c", "kind": "keyword", "count": 80, "secs": 40} and r["pending"] == ["d", "e"]


def test_scan_records_progress(ext, fake):
    ext.dev(fake.base)
    ext.post("/api/scan", {"keywords": ["gadget", "lamp"], "max_ads": 50})
    ext.wait_idle()
    p = ext.get("/api/jobs")["progress"]
    assert [d["title"] for d in p["done"]] == ["Quét 'gadget'", "Quét 'lamp'"] and p["total"] == 2
    assert p["done"][0]["n"] == 5 and p["items"] >= 5 and p["eta_s"] == 0


def test_dashboard_cards_shopify_and_keyword_tabs(ext):
    page = ext.page
    ext.post("/api/demo")
    page.evaluate("v => setView(v)", "overview")
    page.wait_for_selector(".vcard .ring")
    assert page.locator(".vcard").count() == ext.get("/api/videos?tab=hot&limit=10")["total"] >= 3
    card = page.locator(".vcard").first
    assert "Video đăng" in card.inner_text() and card.locator("text=Phân tích").count() == 1
    page.once("dialog", lambda d: d.dismiss())                       # chưa kết nối -> hỏi mở trang Kết nối, bấm Huỷ
    card.locator("text=Clone").click()
    page.wait_for_timeout(400)
    assert "hidden" in page.get_attribute("#drawer", "class")          # bấm nút trong thẻ không mở bảng chi tiết
    card.locator("text=Phân tích").click()
    page.wait_for_selector("#drawer:not(.hidden) >> text=Clone vào Shopify")
    page.evaluate("v => setView(v)", "shopify")
    page.wait_for_selector("#shopifyForm")
    assert "write_products,read_products" in page.inner_text("#content")
    page.evaluate("v => setView(v)", "scan")
    page.wait_for_selector("#kwBox >> text=fireplace decor")
    assert "+264%" in page.inner_text("#kwBox") and page.locator("#progress").count() == 1
    page.click("#kwBox >> text=Google Trends")
    page.wait_for_selector("#kwBox >> text=halloween costumes")
    page.evaluate("v => setView(v)", "potential")
    page.evaluate("l => setLayout(l)", "grid")
    page.wait_for_selector(".vcard")
    page.evaluate("l => setLayout(l)", "list")
    assert ext.errors == []
