"""Nâng cấp 3 trong tiện ích: tải ảnh / video bằng trình tải của Chrome, video viral theo thị trường
(TikTok thịnh hành, hashtag xu hướng), giống hệt bản app."""
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from conftest import jpeg
from snakepod import social

NOW = 1_760_000_000


def test_trend_parsers_and_labels_match_python(ext):
    videos = json.dumps({"data": {"videos": [
        {"item_id": "7401", "item_url": "https://www.tiktok.com/@a/video/7401", "cover": "https://c/1.jpg", "title": "Dog mum hoodie",
         "duration": 18.5, "country_code": "gb", "region": "United Kingdom"},
        {"item_id": 7402, "cover": "https://c/2.jpg", "title": {"text": "Nurse mug"}},
        {"id": "ad1", "ad_title": "Top ad", "video_info": {"cover": "c"}},
        {"id": "9", "stats": {"playCount": 5}, "desc": "video thường"},
        {"item_id": "x", "item_url": "https://evil.example/v"}]}})
    py, js = social.parse_trend_videos_text(videos), ext.js("t => SP.social.parseTrendVideosText(t)", videos)
    assert [json.loads(x.pop("extra") or "null") for x in py] == [json.loads(x.pop("extra") or "null") for x in js]
    assert py == js and len(py) == 2
    tags = json.dumps({"data": {"list": [
        {"hashtag_name": "DogMom", "rank": 1, "rank_diff": 3, "video_views": 98000000, "publish_cnt": 41000,
         "trend": [{"time": NOW - 86400, "value": 0.4}, {"time": NOW, "value": 1}], "country_info": {"id": "US"}},
        {"hashtag_name": "##halloweendecor", "rank": "2", "video_views": "64M", "trend": "x"}, {"hashtag_name": " "}]}})
    assert social.parse_hashtags_text(tags) == ext.js("t => SP.social.parseHashtagsText(t)", tags)
    rnd = random.Random(5)
    for i in range(20):
        row = {"vid": f"tiktok_trend:{i}", "platform": "tiktok_trend", "views": None, "likes": None, "comments": None,
               "shares": None, "created_ts": None, "caption": rnd.choice(["Dog mom tee", None]), "extra": None,
               "market": rnd.choice(["US", "GB", None]), "keyword": None, "first_seen": NOW, "last_seen": NOW}
        assert social.summarize(row, [], now=NOW) == ext.js("([r, t]) => SP.social.summarize(r, [], t)", [row, NOW])


@pytest.fixture
def media_server():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if "expired" in self.path:
                return self.send_error(403)
            body, ctype = (b"\x00\x00\x00\x18ftypmp42video", "video/mp4") if ".mp4" in self.path else (jpeg([1, 0, 1]), "image/jpeg")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def _wait_download(ext, did, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        [d] = ext.js("id => chrome.downloads.search({id})", did)
        if d["state"] != "in_progress":
            return d
        time.sleep(0.2)
    raise AssertionError("tải chưa xong")


def test_download_media_with_chrome(ext, media_server, tmp_path):
    base = media_server.base
    gone = f"{base}/expired.mp4?oe={int(time.time()) - 3600:X}"
    ad = lambda i, body, video, thumb: {"ad_id": i, "collation_id": None, "collation_count": 1, "page_id": "p" + i, "page_name": "P",
                                        "start_ts": NOW, "end_ts": None, "is_active": 1, "title": None, "body": body,
                                        "link_url": f"https://s{i}.com/products/p", "domain": f"s{i}.com", "thumb_url": thumb,
                                        "video_url": video}
    ext.js("""async ([a, b]) => {
      await SP.db.upsertAds([a, b]);
      await SP.db.saveThumb('2.jpg', 'data:image/jpeg;base64,/9j/2Q==');
      await SP.db.setThumb('1', null, 'aaaaaaaaaaaaaaaa');
      await SP.db.setThumb('2', '2.jpg', '5555555555555555');
      await SP.jobs.recompute();
    }""", [ad("1", "Nurse mug gift", f"{base}/v1.mp4", f"{base}/t1.jpg"), ad("2", "Dog shirt", gone, f"{base}/expired.jpg?oe=1")])
    r = ext.get("/api/media/ad/1?type=video")
    assert r["filename"].startswith("SnakemediaPOD/") and r["filename"].endswith("/qc-1-nurse-mug-gift.mp4")
    d = _wait_download(ext, r["id"])
    assert d["state"] == "complete" and d["mime"] == "video/mp4"
    bad = ext.call("GET", "/api/media/ad/2?type=video", ok=False)
    assert bad["status"] == 502 and "hết hạn" in bad["detail"]
    r = ext.get("/api/media/ad/2?type=image")                          # link ảnh hết hạn -> ảnh lưu trong tiện ích
    assert _wait_download(ext, r["id"])["state"] == "complete"
    assert ext.call("GET", "/api/media/ad/404?type=video", ok=False)["status"] == 404
    v = ext.get("/api/videos/2")
    assert v["media"]["video_expired"] and v["media"]["video_expires_ts"] < time.time()
    assert {a["ad_id"]: a["video_url"] for a in v["ads"]}["2"] == gone
    assert ext.call("POST", "/api/media/batch", {"cids": []}, ok=False)["status"] == 400
    before = len(ext.js("() => chrome.downloads.search({})"))
    assert ext.post("/api/media/batch", {"cids": ["1", "2"], "kind": "both"})["queued"] == 1
    ext.wait_idle()
    assert "Đã gửi 3 file" in ext.get("/api/jobs")["log"][-2]["msg"]   # 2 ảnh + 1 video (video QC 2 hết hạn)
    assert len(ext.js("() => chrome.downloads.search({})")) == before + 3


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
                self._send(jpeg([1, 0, 1, 0, 1, 0, 1, 0, 1]), "image/jpeg")
            else:
                self.send_error(404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.state = state
    srv.base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def test_scan_trends_by_market(ext, fake_cc):
    ext.dev(fake_cc.base)
    r = ext.post("/api/viral/scan", {"platform": "tiktok_trend", "countries": ["DE"], "save": True})
    assert r["queued"] == 1
    ext.wait_idle()
    assert any("countryCode=DE" in p for p in fake_cc.state["paths"])
    v = ext.get("/api/viral?market=DE")
    assert sorted(x["vid"] for x in v["items"]) == ["tiktok_trend:v1", "tiktok_trend:v2"] and v["markets"] == {"DE": 2}
    assert all(x["label"] == "xu_huong" and x["cover_src"] for x in v["items"])
    ext.post("/api/viral/scan", {"platform": "tiktok_tags", "countries": ["FR"]})
    ext.wait_idle()
    t = ext.get("/api/trends")
    assert [(x["market"], x["name"], x["rank"]) for x in t["items"]] == [("FR", "tag1", 1), ("FR", "tag2", 2)]
    assert ("tiktok_trend", "", "DE") in {(k["platform"], k["keyword"], k["country"]) for k in ext.get("/api/viral/keywords")}


def test_markets_api_and_new_views(ext):
    ext.post("/api/demo")
    m = ext.get("/api/markets")
    assert m["markets"]["GB"] == "Anh" and m["market_sources"] == ["tiktok_ads", "tiktok_tags", "tiktok_trend"]
    t = ext.get("/api/trends")
    dog = next(x for x in t["items"] if x["name"] == "dogmom")
    assert t["markets"] == ["GB", "US"] and dog["match"] == ["dog", "mom"] and dog["move"] == 0 and len(dog["trend"]) == 7
    page = ext.page
    for view in ["trends", "viral", "sap_win"]:
        page.evaluate("v => setView(v)", view)
        page.wait_for_timeout(400)
        assert "Lỗi" not in page.inner_text("#content"), view
    page.evaluate("v => setView(v)", "trends")
    page.wait_for_selector("text=#dogmom")
    page.evaluate("v => setView(v)", "viral")
    page.wait_for_selector("#viralForm [name=countries][value=GB]")
    page.evaluate("v => setView(v)", "sap_win")
    page.wait_for_selector(".mediabar")
    assert ext.get("/api/viral?market=GB")["items"][0]["vid"] == "tiktok_trend:7401"
    assert ext.errors == []
    # quét thật đầu tiên sẽ xoá dữ liệu mẫu, nên kiểm tra xếp hàng cuối cùng
    ext.dev("http://127.0.0.1:9")                                       # trang quét không mở được -> việc kết thúc nhanh
    ext.js("SP.db.setSetting('demo', false)")                          # giữ từ khoá theo dõi (không xoá dữ liệu mẫu)
    r = ext.post("/api/viral/scan", {"platform": "tiktok_ads", "keywords": ["mug", "shirt"], "countries": ["US", "gb", "US"], "save": True})
    assert r["queued"] == 4
    assert ext.post("/api/viral/scan", {"platform": "tiktok", "keywords": ["#dogmom"], "countries": ["US", "GB"]})["queued"] == 1
    assert ext.call("POST", "/api/viral/scan", {"platform": "tiktok", "keywords": []}, ok=False)["status"] == 400
    kws = {(k["platform"], k["keyword"], k["country"]) for k in ext.get("/api/viral/keywords")}
    assert {("tiktok_ads", "mug", "GB"), ("tiktok_ads", "shirt", "US")} <= kws
    ext.call("DELETE", "/api/viral/keywords/tiktok_ads/mug?country=GB")
    kws = {(k["platform"], k["keyword"], k["country"]) for k in ext.get("/api/viral/keywords")}
    assert ("tiktok_ads", "mug", "GB") not in kws and ("tiktok_ads", "mug", "US") in kws
    ext.wait_idle()
