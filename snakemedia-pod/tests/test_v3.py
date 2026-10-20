"""Nâng cấp 3: tải ảnh / video QC, video viral theo thị trường (TikTok thịnh hành, hashtag xu hướng, Top Ads)."""
import importlib
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from snakepod import media, social

NOW = 1_760_000_000


def test_link_expiry():
    url = f"https://video.fbcdn.net/v/x.mp4?_nc_ht=x&oe={NOW:X}"
    assert media.link_expiry(url) == NOW
    assert media.expired(url, now=NOW + 1) and not media.expired(url, now=NOW - 1)
    assert media.link_expiry("https://x/y.mp4") is None and not media.expired("https://x/y.mp4")
    assert media.slug("Personalized Dog Mom Shirt 🐶 Custom!") == "personalized-dog-mom-shirt-custom"


def test_parse_creative_center_trends():
    videos = json.dumps({"data": {"videos": [
        {"item_id": "7401", "item_url": "https://www.tiktok.com/@a/video/7401", "cover": "https://c/1.jpg", "title": "Dog mum hoodie",
         "duration": 18, "country_code": "gb", "region": "United Kingdom"},
        {"id": "ad1", "ad_title": "Top ad, không phải video thịnh hành", "video_info": {"cover": "c"}},
        {"id": "9", "stats": {"playCount": 5}, "desc": "video TikTok thường"}]}})
    [v] = social.parse_trend_videos_text(videos)
    assert v["vid"] == "tiktok_trend:7401" and v["market"] == "GB" and v["caption"] == "Dog mum hoodie" and v["duration"] == 18
    tags = json.dumps({"data": {"list": [
        {"hashtag_name": "DogMom", "rank": 1, "rank_diff": 3, "video_views": 98000000, "publish_cnt": 41000,
         "trend": [{"time": NOW - 86400, "value": 0.4}, {"time": NOW, "value": 1}], "country_info": {"id": "US"}},
        {"hashtag_name": "#halloweendecor", "rank": "2", "video_views": "64M"}]}})
    t = {x["name"]: x for x in social.parse_hashtags_text(tags)}
    assert set(t) == {"dogmom", "halloweendecor"} and t["dogmom"]["views"] == 98_000_000 and t["dogmom"]["market"] == "US"
    assert t["dogmom"]["trend"] == [[NOW - 86400, 0.4], [NOW, 1]] and t["halloweendecor"]["views"] == 64_000_000
    row = {**v, "keyword": None, "first_seen": NOW, "last_seen": NOW, "cover_path": None}
    s = social.summarize(row, [], now=NOW)
    assert s["label"] == "xu_huong" and "thị trường GB" in s["checks"][0]["text"]


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    monkeypatch.setenv("SNAKEPOD_MEDIA", str(tmp_path / "media"))
    from snakepod import config
    importlib.reload(config)
    from snakepod import analyze, db, demo, jobs, media as md, server
    for m in (db, analyze, md, jobs, demo, server):
        importlib.reload(m)
    return tmp_path


def test_old_social_watch_table_is_upgraded(app_env):
    from snakepod import config, db
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.DB_PATH) as c:
        c.execute("CREATE TABLE social_watch (platform TEXT, keyword TEXT, country TEXT, added_ts INTEGER, "
                  "last_scan_ts INTEGER, PRIMARY KEY (platform, keyword))")
        c.execute("INSERT INTO social_watch VALUES ('tiktok_ads', '', 'US', 1, NULL)")
    db.init()
    db.add_social_watch("tiktok_ads", "", "GB")            # cùng từ khoá, thị trường khác -> thêm được
    assert [(w["keyword"], w["country"]) for w in db.list_social_watch()] == [("", "GB"), ("", "US")]
    db.remove_social_watch("tiktok_ads", "", "GB")
    assert [w["country"] for w in db.list_social_watch()] == ["US"]


@pytest.fixture
def media_server():
    hits = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            hits.append(self.path)
            if "expired" in self.path:
                self.send_error(403)
                return
            body, ctype = (b"\x00\x00\x00\x18ftypmp42video", "video/mp4") if ".mp4" in self.path else (b"\xff\xd8jpeg", "image/jpeg")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.base, srv.hits = f"http://127.0.0.1:{srv.server_address[1]}", hits
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def test_media_download_and_batch(app_env, media_server, monkeypatch):
    from snakepod import config, db, jobs, server
    db.init()
    base = media_server.base
    gone = f"{base}/expired.mp4?oe={int(time.time()) - 3600:X}"
    ads = [{"ad_id": "1", "collation_id": None, "collation_count": 1, "page_id": "p", "page_name": "P", "start_ts": NOW,
            "end_ts": None, "is_active": 1, "title": None, "body": "Nurse mug gift", "link_url": "https://a.com/products/p",
            "domain": "a.com", "thumb_url": f"{base}/t1.jpg", "video_url": f"{base}/v1.mp4"},
           {"ad_id": "2", "collation_id": None, "collation_count": 1, "page_id": "q", "page_name": "Q", "start_ts": NOW,
            "end_ts": None, "is_active": 1, "title": None, "body": "Dog shirt", "link_url": "https://b.com/products/q",
            "domain": "b.com", "thumb_url": f"{base}/expired.jpg", "video_url": gone}]
    db.upsert_ads(ads)
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    (config.THUMB_DIR / "2.jpg").write_bytes(b"\xff\xd8saved")
    db.set_thumb("1", None, "aaaaaaaaaaaaaaaa")
    db.set_thumb("2", "2.jpg", "5555555555555555")
    jobs.recompute()
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda kind, title, fn: queued.append(fn) or True)
    with TestClient(server.app) as c:
        r = c.get("/api/media/ad/1", params={"type": "video"})
        assert r.status_code == 200 and r.content.startswith(b"\x00\x00\x00\x18ftyp")
        assert 'filename="qc-1-nurse-mug-gift.mp4"' in r.headers["content-disposition"]
        r = c.get("/api/media/ad/2", params={"type": "video"})
        assert r.status_code == 502 and "hết hạn" in r.json()["detail"]
        r = c.get("/api/media/ad/2", params={"type": "image"})              # link ảnh hỏng -> ảnh đã lưu trong máy
        assert r.status_code == 200 and r.content == b"\xff\xd8saved"
        assert c.get("/api/media/ad/404", params={"type": "video"}).status_code == 404
        d = c.get("/api/videos/2").json()
        assert d["media"]["video_expired"] and d["media"]["video_expires_ts"] < time.time()
        assert {a["ad_id"]: a["video_url"] for a in d["ads"]}["2"] == gone
        assert c.post("/api/media/batch", json={"cids": [], "vids": []}).status_code == 400
        r = c.post("/api/media/batch", json={"cids": ["1", "2"], "kind": "both"}).json()
        assert r["queued"] == 1
    assert queued[0]() == 3                                            # 2 ảnh + 1 video (video QC 2 hết hạn)
    files = sorted(p.name for p in (app_env / "media").rglob("*") if p.is_file())
    assert len(files) == 3 and sum(f.endswith(".mp4") for f in files) == 1


def test_viral_scan_by_markets_and_trends_api(app_env, monkeypatch):
    from snakepod import db, demo, jobs, server
    demo.main()
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda kind, title, fn: queued.append(title) or True)
    with TestClient(server.app) as c:
        m = c.get("/api/markets").json()
        assert m["markets"]["GB"] == "Anh" and "tiktok_trend" in m["market_sources"]
        r = c.post("/api/viral/scan", json={"platform": "tiktok_ads", "keywords": ["mug", "shirt"],
                                            "countries": ["US", "gb", "US"], "save": True}).json()
        assert r["queued"] == 4 and "Viral tiktok_ads 'mug' GB" in queued
        queued.clear()
        r = c.post("/api/viral/scan", json={"platform": "tiktok", "keywords": ["#dogmom"], "countries": ["US", "GB"]}).json()
        assert r["queued"] == 1 and queued == ["Viral tiktok '#dogmom'"]          # tìm kiếm thường: 1 lần
        assert c.post("/api/viral/scan", json={"platform": "tiktok", "keywords": []}).status_code == 400
        assert c.post("/api/viral/scan", json={"platform": "tiktok_tags", "countries": ["DE"]}).json()["queued"] == 1
        kws = {(k["platform"], k["keyword"], k["country"]) for k in c.get("/api/viral/keywords").json()}
        assert {("tiktok_ads", "mug", "GB"), ("tiktok_ads", "shirt", "US")} <= kws
        c.delete("/api/viral/keywords/tiktok_ads/mug", params={"country": "GB"})
        kws = {(k["platform"], k["keyword"], k["country"]) for k in c.get("/api/viral/keywords").json()}
        assert ("tiktok_ads", "mug", "GB") not in kws and ("tiktok_ads", "mug", "US") in kws

        t = c.get("/api/trends").json()
        assert t["markets"] == ["GB", "US"]
        dog = next(x for x in t["items"] if x["name"] == "dogmom")
        assert dog["match"] == ["dog", "mom"] and dog["move"] == 0 and len(dog["trend"]) == 7
        assert next(x for x in t["items"] if x["name"] == "nursesoftiktok")["move"] == 1        # hạng 2 -> 1... (2-1)
        assert [x["market"] for x in c.get("/api/trends", params={"market": "GB"}).json()["items"]] == ["GB"] * 3
        v = c.get("/api/viral", params={"market": "GB"}).json()
        assert v["markets"] == {"GB": 1} and [x["vid"] for x in v["items"]] == ["tiktok_trend:7401"]
        assert v["items"][0]["label"] == "xu_huong"


from tests.test_e2e import _chromium, _jpeg  # noqa: E402


@pytest.fixture
def fake_cc():
    state = {"pages": {"video": 0, "hashtag": 0}, "paths": []}

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
            state["paths"].append(self.path)
            if path in ("/trend-video", "/trend-hashtag"):
                kind = path.split("-")[1]
                self._send(f"""<html><body style="height:3000px"><button id="more">View More</button>
<script>document.querySelector('#more').onclick = () => fetch('/creative_radar_api/v1/popular_trend/{kind}/list?page=2');
fetch('/creative_radar_api/v1/popular_trend/{kind}/list?page=1');</script></body></html>""")
            elif path.startswith("/creative_radar_api/v1/popular_trend/video"):
                state["pages"]["video"] += 1
                n = state["pages"]["video"]
                vids = [{"item_id": f"v{n}", "item_url": f"https://www.tiktok.com/@x/video/v{n}", "title": f"Trend {n}",
                         "cover": f"http://127.0.0.1:{port}/cover.jpg", "country_code": "DE"}] if n <= 2 else []
                self._send(json.dumps({"data": {"videos": vids}}), "application/json")
            elif path.startswith("/creative_radar_api/v1/popular_trend/hashtag"):
                state["pages"]["hashtag"] += 1
                n = state["pages"]["hashtag"]
                tags = [{"hashtag_name": f"tag{n}", "rank": n, "video_views": 1000 * n, "publish_cnt": 10 * n}] if n <= 2 else []
                self._send(json.dumps({"data": {"list": tags}}), "application/json")
            elif path == "/cover.jpg":
                self._send(_jpeg([1, 0, 1, 0, 1, 0, 1, 0, 1]), "image/jpeg")
            else:
                self.send_error(404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.state = state
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


@pytest.mark.skipif(_chromium() is None, reason="không có Chromium")
def test_scan_creative_center_trends_by_market(app_env, monkeypatch, fake_cc):
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
    monkeypatch.setitem(safety.DEFAULT_LIMITS, "tiktok", {"min_gap_s": 0, "max_per_day": 100})
    base = f"http://127.0.0.1:{fake_cc.server_address[1]}"
    monkeypatch.setattr(scraper, "TREND_VIDEOS", base + "/trend-video")
    monkeypatch.setattr(scraper, "TREND_TAGS", base + "/trend-hashtag")
    db.init()
    assert jobs.social_job("tiktok_trend", "", "DE", 50)() == 2
    assert any("countryCode=DE" in p for p in fake_cc.state["paths"])             # đúng thị trường trên link
    rows = {r["vid"]: r for r in db.social_rows("tiktok_trend")}
    assert set(rows) == {"tiktok_trend:v1", "tiktok_trend:v2"} and all(r["market"] == "DE" for r in rows.values())
    assert all(r["cover_path"] for r in rows.values())
    assert jobs.social_job("tiktok_tags", "", "FR", 50)() == 2
    assert [(t["market"], t["name"], t["rank"]) for t in db.list_trends()] == [("FR", "tag1", 1), ("FR", "tag2", 2)]
