"""Test chế độ Video viral: đọc dữ liệu TikTok / Top Ads / Reels, chấm nhãn, API, QC đang lan nhanh,
và quét thật bằng Chromium trên trang TikTok + Creative Center GIẢ."""
import importlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from snakepod import analyze, social

HOUR = 3600
NOW = 1_760_000_000


def _tt(item_id, views, age_h, desc="Personalized dog mom shirt #dogmom", likes=1000, shares=100):
    return {"id": item_id, "desc": desc, "createTime": NOW - age_h * HOUR, "author": {"uniqueId": "shop1"},
            "stats": {"playCount": views, "diggCount": likes, "commentCount": 10, "shareCount": shares,
                      "collectCount": 5},
            "statsV2": {"playCount": str(views)}, "video": {"cover": "https://p16.tiktokcdn.com/c.jpg", "duration": 15}}


def test_parse_tiktok_search_and_html():
    text = json.dumps({"item_list": [_tt("1", 5000, 10)], "data": [{"type": 1, "item": _tt("2", 900, 5)}]})
    items = {i["item_id"]: i for i in social.parse_tiktok_text(text)}
    assert set(items) == {"1", "2"}
    a = items["1"]
    assert a["vid"] == "tiktok:1" and a["views"] == 5000 and a["likes"] == 1000 and a["author"] == "shop1"
    assert a["url"] == "https://www.tiktok.com/@shop1/video/1" and a["created_ts"] == NOW - 10 * HOUR
    html = ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            + json.dumps({"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": _tt("3", 7, 1)}}}})
            + "</script>")
    assert [i["item_id"] for i in social.parse_tiktok_html(html)] == ["3"]


def test_parse_topads():
    text = json.dumps({"code": 0, "data": {"materials": [{
        "id": "77", "ad_title": "Custom pet portrait canvas", "brand_name": "PawCanvas", "like": 54000, "ctr": 0.12,
        "cost": 3, "industry_key": "label_home", "video_info": {"vid": "v1", "cover": "https://x/c.jpg",
                                                               "video_url": {"720p": "https://x/v.mp4"}, "duration": 21.5}}]}})
    [it] = social.parse_topads_text(text)
    assert it["vid"] == "tiktok_ads:77" and it["likes"] == 54000 and it["video_url"] == "https://x/v.mp4"
    assert json.loads(it["extra"]) == {"brand_name": "PawCanvas", "ctr": 0.12, "cost": 3, "industry_key": "label_home"}


def test_parse_reels():
    text = json.dumps({"data": {"node": {"id": "r1", "play_count": 350000, "creation_time": NOW - 40 * HOUR,
                                         "owner": {"name": "Forever Prints"}, "permalink_url": "https://fb.com/reel/r1",
                                         "message": {"text": "Memorial canvas"}, "feedback": {"reaction_count": {"count": 1800},
                                                                                          "share_count": {"count": 61}}}}})
    [it] = social.parse_reels_text(text)
    assert it["views"] == 350000 and it["author"] == "Forever Prints" and it["likes"] == 1800 and it["shares"] == 61
    assert it["url"] == "https://fb.com/reel/r1" and it["caption"] == "Memorial canvas"


def _row(views, age_h, platform="tiktok", **kw):
    return {"vid": f"{platform}:x", "platform": platform, "views": views, "likes": 100, "comments": 5, "shares": 10,
            "created_ts": NOW - age_h * HOUR if age_h is not None else None, "caption": "Nurse mug", "extra": None, **kw}


def test_labels_use_real_growth_between_scans():
    # trung bình chỉ 1.000 xem/giờ nhưng 2 lần quét gần nhất cho thấy 30.000 xem/giờ -> Đang nổ
    v = social.summarize(_row(48_000 + 180_000, 48), [(NOW - 6 * HOUR, 48_000, 0, 0, 0), (NOW, 228_000, 0, 0, 0)], now=NOW)
    assert v["recent_vph"] == 30_000 and v["label"] == "dang_no"
    assert social.summarize(_row(2_000_000, 24 * 10), [], now=NOW)["label"] == "viral"
    assert social.summarize(_row(100_000, 24), [], now=NOW)["label"] == "dang_len"        # ~4.166/giờ
    assert social.summarize(_row(100_000, 24 * 30), [], now=NOW)["label"] == "binh_thuong"
    assert social.summarize(_row(None, None), [], now=NOW)["label"] == "binh_thuong"
    top = social.summarize(_row(None, None, platform="tiktok_ads", extra='{"ctr": "Top 5%"}'), [], now=NOW)
    assert top["label"] == "top_ads" and top["product_type"] == "Cốc / Ly" and top["niches"] == ["Y tá / Bác sĩ"]


def test_facebook_ads_spreading():
    def ad(i, domain, age_h):
        return {"ad_id": str(i), "domain": domain, "page_id": domain, "start_ts": NOW - age_h * HOUR, "is_active": 1,
                "collation_count": 1, "link_url": f"https://{domain}/products/p", "body": "x"}
    v = analyze.summarize("c", [ad(1, "a.com", 200), ad(2, "b.com", 20), ad(3, "c.com", 5)], {}, now=NOW)
    assert v["ads_new_48h"] == 2 and v["shops_new_48h"] == 2 and v["spreading"]
    v = analyze.summarize("c", [ad(1, "a.com", 200), ad(2, "a.com", 20)], {}, now=NOW)
    assert v["ads_new_48h"] == 1 and v["shops_new_48h"] == 0 and not v["spreading"]


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import db, demo, jobs, server
    for m in (db, jobs, demo, server):
        importlib.reload(m)
    return tmp_path


def test_viral_api(app_env, monkeypatch):
    from snakepod import demo, jobs, server
    demo.main()
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda kind, title, fn: queued.append(title) or True)
    with TestClient(server.app) as c:
        res = c.get("/api/viral").json()
        assert res["counts"]["dang_no"] >= 1 and res["counts"]["top_ads"] == 2
        vphs = [v["sort_vph"] for v in res["items"]]
        assert vphs == sorted(vphs, reverse=True)
        ads = c.get("/api/viral", params={"platform": "tiktok_ads"}).json()["items"]
        assert len(ads) == 2 and all(v["label"] == "top_ads" for v in ads)
        dog = c.get("/api/viral", params={"niche": "Chó", "platform": "tiktok"}).json()["items"]
        assert len(dog) == 1 and dog[0]["label"] == "dang_no"
        detail = c.get(f"/api/viral/{dog[0]['vid']}").json()
        assert len(detail["snapshots"]) == 2 and detail["recent_vph"] is not None
        assert c.get("/api/viral/tiktok:nope").status_code == 404

        assert c.post("/api/viral/scan", json={"platform": "bad", "keyword": "x"}).status_code == 400
        assert c.post("/api/viral/scan", json={"platform": "tiktok", "keyword": " "}).status_code == 400
        assert c.post("/api/viral/scan", json={"platform": "tiktok_ads", "keyword": "", "save": True}).status_code == 200
        assert c.post("/api/viral/scan", json={"platform": "fb_reels", "keyword": "nurse mug", "save": True}).status_code == 200
        assert len(queued) == 2
        kws = {(k["platform"], k["keyword"]) for k in c.get("/api/viral/keywords").json()}
        assert ("fb_reels", "nurse mug") in kws and ("tiktok_ads", "") in kws
        c.delete("/api/viral/keywords/tiktok_ads/%20")          # Top Ads không từ khoá
        c.delete("/api/viral/keywords/fb_reels/nurse mug")
        kws = {(k["platform"], k["keyword"]) for k in c.get("/api/viral/keywords").json()}
        assert ("fb_reels", "nurse mug") not in kws and ("tiktok_ads", "") not in kws

        spread = c.get("/api/videos", params={"spread": "true"}).json()["items"]
        assert spread and all(v["spreading"] for v in spread)


# ---------- quét thật bằng Chromium trên trang GIẢ ----------

from tests.test_e2e import _chromium, _jpeg  # noqa: E402


@pytest.fixture
def fake_sites():
    state = {"search_pages": 0, "topads_pages": 0, "typed": None}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="text/html"):
            body = body.encode() if isinstance(body, str) else body
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            port = self.server.server_address[1]
            path = self.path.split("?")[0]
            now = int(time.time())

            def tt(i, views, age_h):
                d = _tt(str(i), views, 0)
                d["createTime"] = now - age_h * HOUR
                d["video"]["cover"] = f"http://127.0.0.1:{port}/cover.jpg"
                return d
            if path == "/search/video":
                ssr = json.dumps({"__DEFAULT_SCOPE__": {"search": {"items": [tt(1, 2_000_000, 100)]}}})
                self._send(f"""<html><body style="height:20000px">
<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{ssr}</script>
<script>let busy=false;window.addEventListener('scroll',async()=>{{if(busy)return;busy=true;
await fetch('/api/search/item/full/?cursor=1');busy=false;}});</script></body></html>""")
            elif path.startswith("/api/search/item/full"):
                state["search_pages"] += 1
                items = [tt(2, 50_000, 5), tt(3, 900, 200)] if state["search_pages"] == 1 else []
                self._send(json.dumps({"item_list": items}), "application/json")
            elif path == "/topads":
                self._send("""<html><body style="height:3000px">
<input placeholder="Search by keyword or brand" onkeydown="if(event.key==='Enter'){fetch('/creative_radar_api/v1/top_ads/v2/list?keyword='+encodeURIComponent(this.value))}">
<button onclick="fetch('/creative_radar_api/v1/top_ads/v2/list?page=2')">View More</button></body></html>""")
            elif path.startswith("/creative_radar_api"):
                state["topads_pages"] += 1
                if "keyword=" in self.path:
                    state["typed"] = self.path.split("keyword=")[1]
                page = state["topads_pages"]
                mats = [{"id": f"ad{page}", "ad_title": f"Custom mug {page}", "brand_name": "MugCo", "like": 1000 * page,
                         "video_info": {"cover": f"http://127.0.0.1:{port}/cover.jpg", "video_url": {"720p": "v"}}}] if page <= 2 else []
                self._send(json.dumps({"data": {"materials": mats}}), "application/json")
            elif path == "/cover.jpg":
                self._send(_jpeg([1, 0, 1, 1, 0, 0, 1, 0, 1]), "image/jpeg")
            else:
                self.send_error(404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.state = state
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


@pytest.mark.skipif(_chromium() is None, reason="không có Chromium")
def test_scan_tiktok_and_topads_against_fake_sites(app_env, monkeypatch, fake_sites):
    monkeypatch.setenv("SNAKEPOD_HEADLESS", "1")
    monkeypatch.setenv("SNAKEPOD_SCROLL_MS", "300,600")
    from snakepod import safety
    monkeypatch.setitem(safety.DEFAULT_LIMITS, "tiktok", {"min_gap_s": 0, "max_per_day": 100})
    if _chromium():
        monkeypatch.setenv("SNAKEPOD_CHROMIUM", _chromium())
    monkeypatch.delenv("SNAKEPOD_PROXY", raising=False)
    from snakepod import config
    importlib.reload(config)
    monkeypatch.setattr(config, "PROXY_FILE", app_env / "proxy.txt")
    from snakepod import db, jobs, scraper
    for m in (db, scraper, jobs):
        importlib.reload(m)
    base = f"http://127.0.0.1:{fake_sites.server_address[1]}"
    monkeypatch.setattr(scraper, "TIKTOK", base)
    monkeypatch.setattr(scraper, "CREATIVE_CENTER", base + "/topads")
    db.init()

    assert jobs.social_job("tiktok", "dog mom shirt", "US", 50)() == 3
    assert jobs.social_job("tiktok_ads", "mug", "US", 50)() == 2
    assert fake_sites.state["typed"] == "mug"            # đã gõ từ khoá vào ô tìm kiếm
    rows = {r["vid"]: r for r in db.social_rows()}
    assert set(rows) == {"tiktok:1", "tiktok:2", "tiktok:3", "tiktok_ads:ad1", "tiktok_ads:ad2"}
    assert all(r["cover_path"] for r in rows.values())    # ảnh bìa đã tải về
    labels = {vid: social.summarize(r, [])["label"] for vid, r in rows.items()}
    assert labels["tiktok:1"] == "viral" and labels["tiktok:2"] == "dang_len" and labels["tiktok:3"] == "binh_thuong"
