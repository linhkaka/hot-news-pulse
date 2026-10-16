"""Gom video (nhanh + thông minh hơn), tải song song, gói chẩn đoán, thông báo, phân trang."""
import importlib
import io
import json
import random
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi.testclient import TestClient

from snakepod import analyze
from tests.test_e2e import _chromium, _jpeg

NOW = 1_760_000_000
DAY = 86400


def test_near_pairs_matches_brute_force():
    rnd = random.Random(7)
    hs = [rnd.getrandbits(64) for _ in range(400)]
    for k in range(120):                               # cài sẵn các hash lệch 0..9 bit
        h = hs[k]
        for _ in range(k % 10):
            h ^= 1 << rnd.randrange(64)
        hs.append(h)
    for d in (6, 12):
        brute = {(i, j) for i in range(len(hs)) for j in range(i + 1, len(hs)) if (hs[i] ^ hs[j]).bit_count() <= d}
        assert analyze.near_pairs(hs, d) == brute and brute


def test_text_and_product_keys():
    assert analyze.text_key("🔥 Personalized Dog Mom Shirt — custom name!!") == "personalized dog mom shirt custom name"
    assert analyze.text_key("Buy now") is None
    assert analyze.product_key("https://a.com/products/personalized-dog-mom-shirt-2?v=1") == "personalized-dog-mom-shirt"
    assert analyze.product_key("https://a.com/products/tshirt") is None            # quá chung chung
    assert analyze.product_key("https://a.com/collections/all") is None


def _ad(i, dhash, body="x", link=None):
    return {"ad_id": str(i), "dhash": dhash, "body": body, "link_url": link, "domain": "a.com", "page_id": "p",
            "start_ts": NOW - DAY, "is_active": 1, "collation_count": 1}


def _flip(h, n):
    v = int(h, 16)
    for b in range(n):
        v ^= 1 << (b * 5)
    return f"{v:016x}"


def test_cluster_loose_match_needs_same_text_or_product():
    base = "a5a5a5a5a5a5a5a5"
    far = _flip(base, 10)                              # lệch 10 bit: quá xa cho mức chặt (6)
    body = "Personalized dog mom shirt with your dog name on it"
    groups = lambda ads: sorted(sorted(a["ad_id"] for a in g) for g in analyze.cluster(ads).values())
    assert groups([_ad(1, base, body), _ad(2, far, body)]) == [["1", "2"]]                 # cùng nội dung
    assert groups([_ad(1, base, "Nurse mug for night shift heroes"), _ad(2, far, body)]) == [["1"], ["2"]]
    link = "https://shop.com/products/custom-pet-portrait-canvas"
    assert groups([_ad(1, base, "a", link), _ad(2, far, "b", link)]) == [["1", "2"]]       # cùng sản phẩm
    assert groups([_ad(1, base, body), _ad(2, _flip(base, 13), body)]) == [["1"], ["2"]]  # quá xa dù cùng chữ


def test_same_product_count_across_videos():
    link = "https://shop.com/products/custom-pet-portrait-canvas"
    ads = [_ad(1, "0" * 16, "video one about pets", link), _ad(2, "f" * 16, "video two totally different", link)]
    vids = analyze.build_videos(ads, {}, now=NOW)
    assert len(vids) == 2 and all(v["product_videos"] == 2 and v["product_key"] == "custom-pet-portrait-canvas" for v in vids)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import db, diag, jobs, notify, safety, server
    for m in (db, diag, notify, safety, jobs, server):
        importlib.reload(m)
    db.init()
    return tmp_path


def test_parallel_thumbnail_download(env, monkeypatch):
    from snakepod import db, jobs
    db.upsert_ads([{"ad_id": str(i), "collation_id": None, "collation_count": 1, "page_id": "p", "page_name": "P",
                    "start_ts": NOW, "end_ts": None, "is_active": 1, "title": None, "body": "b",
                    "link_url": None, "domain": None, "thumb_url": f"https://cdn.x/{i}.jpg", "video_url": None}
                   for i in range(40)])
    seen = set()

    def handler(req):
        seen.add(threading.get_ident())
        time.sleep(0.05)
        if req.url.path == "/13.jpg":
            return httpx.Response(404)
        return httpx.Response(200, content=_jpeg([1, 0, 1, 0, 1, 0, 1, 0, 1]))
    real = httpx.Client
    monkeypatch.setattr(jobs.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
    t = time.time()
    jobs.fetch_thumbs()
    assert time.time() - t < 40 * 0.05                # nhanh hơn tải lần lượt
    assert len(seen) > 1                              # thật sự chạy nhiều luồng
    rows = {a["ad_id"]: a for a in db.all_ads()}
    assert sum(1 for a in rows.values() if a["dhash"]) == 39 and rows["13"]["dhash"] is None


def test_diag_bundle_save_list_zip(env):
    from snakepod import diag
    name = diag.save("fb QC", "https://x/ads", "https://x/ads", "<html>me@mail.com</html>",
                     [("https://x/api", '{"email":"a.b@c.co"}')], "Không đọc được", 0, b"PNG")
    [b] = diag.list_bundles()
    assert b["name"] == name and b["error"] == "Không đọc được" and b["responses"] == 1
    z = zipfile.ZipFile(io.BytesIO(diag.zip_bundle(name)))
    files = {n.split("/")[-1]: z.read(n).decode("utf-8", "ignore") for n in z.namelist()}
    assert set(files) == {"meta.json", "page.html", "responses.jsonl", "screenshot.png"}
    assert "me@mail.com" not in files["page.html"] and "a.b@c.co" not in files["responses.jsonl"]
    assert diag.zip_bundle("../winradar.db") is None and diag.zip_bundle("khong-co") is None
    for i in range(diag.KEEP + 3):
        diag.save(f"x{i}", "u")
    assert len(diag.list_bundles()) == diag.KEEP


@pytest.mark.skipif(_chromium() is None, reason="không có Chromium")
def test_empty_scan_saves_diag_bundle(env, monkeypatch):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = b"<html><title>Ad Library</title><body>No ads match</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("SNAKEPOD_HEADLESS", "1")
        monkeypatch.setenv("SNAKEPOD_SCROLL_MS", "100,200")
        if _chromium():
            monkeypatch.setenv("SNAKEPOD_CHROMIUM", _chromium())
        from snakepod import config
        importlib.reload(config)
        monkeypatch.setattr(config, "PROXY_FILE", env / "proxy.txt")
        from snakepod import diag, scraper
        importlib.reload(scraper)
        logs = []
        assert scraper.run_collect(f"http://127.0.0.1:{srv.server_address[1]}/ads/library/", 10, logs.append) == []
        [b] = diag.list_bundles()
        assert b["items"] == 0 and any("gói chẩn đoán" in m for m in logs)
        files = zipfile.ZipFile(io.BytesIO(diag.zip_bundle(b["name"]))).namelist()
        assert any(f.endswith("screenshot.png") for f in files) and any(f.endswith("page.html") for f in files)
    finally:
        srv.shutdown()


def _tg(calls):
    def handler(req):
        calls.append((req.url.path, json.loads(req.content) if req.content else None))
        if req.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": [{"message": {"chat": {"id": 987}}}]})
        if "badtoken" in req.url.path:
            return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
        return httpx.Response(200, json={"ok": True, "result": {}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def _vid(cid, label, title="Dog mom shirt"):
    return {"cid": cid, "label": label, "title": title, "ad_library_url": f"https://fb/ads?id={cid}",
            "video_age_days": 5, "shops_active": 2, "ads_per_day": 3.2}


def test_notify_only_new_and_batched(env, monkeypatch):
    from snakepod import notify
    monkeypatch.setenv("SNAKEPOD_NO_TOAST", "1")
    calls = []
    client = _tg(calls)
    # chưa có kênh nào: không gửi gì, nhưng vẫn ghi nhận video đã thấy
    assert notify.check_videos([_vid("a", "sap_win")], client=client) == [] and not calls
    notify.save_settings("123:abc", "987", windows=False)
    assert notify.public_settings()["token_hint"] == "…:abc" and "telegram_token" not in notify.public_settings()
    assert notify.check_videos([_vid("a", "sap_win")], client=client) == []                  # 'a' đã thấy từ trước
    sent = notify.check_videos([_vid("a", "sap_win")] + [_vid(f"n{i}", "sap_win", "<b>x</b>") for i in range(7)],
                               client=client)
    assert sent == ["telegram"] and len(calls) == 1
    text = calls[0][1]["text"]
    assert "Sắp WIN mới (7)" in text and "và 2 video khác" in text and "&lt;b&gt;x" in text
    assert notify.check_videos([_vid(f"n{i}", "sap_win") for i in range(7)], client=client) == []   # không báo lại
    notify.save_settings(events={"win": False})
    assert notify.check_videos([_vid("w1", "win")], client=client) == []                      # sự kiện đã tắt
    assert notify.follow_update("bloomyard.com", 3, client=client) == ["telegram"]
    assert notify.find_chat_id("123:abc", client) == "987"
    notify.save_settings("badtoken", "987")
    logs = []
    assert notify.send("x", ["y"], logs.append, client) == [] and "Unauthorized" in logs[0]
    notify.save_settings(telegram_token="")
    assert not notify.public_settings()["has_token"]


def test_notify_api_and_pagination(env, monkeypatch):
    from snakepod import demo, server
    monkeypatch.setenv("SNAKEPOD_NO_TOAST", "1")
    demo.main()
    with TestClient(server.app) as c:
        r = c.post("/api/notify", json={"windows": False})
        assert r.status_code == 200 and r.json()["windows"] is False
        assert c.post("/api/notify/test").status_code == 400                  # chưa có kênh nào
        assert c.post("/api/notify/find-chat").status_code == 400             # chưa có token
        full = c.get("/api/videos").json()
        p1 = c.get("/api/videos", params={"limit": 3, "offset": 0}).json()
        p2 = c.get("/api/videos", params={"limit": 3, "offset": 3}).json()
        assert p1["total"] == full["total"] and len(p1["items"]) == 3
        assert [v["cid"] for v in p1["items"] + p2["items"]] == [v["cid"] for v in full["items"]][:6]
        vir = c.get("/api/viral", params={"limit": 2}).json()
        assert len(vir["items"]) == 2 and vir["total"] > 2
        assert c.get("/api/diag").json() == []
        assert c.get("/api/diag/../../x/download").status_code == 404
