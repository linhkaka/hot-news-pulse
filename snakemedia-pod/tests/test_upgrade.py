"""Test cho bản nâng cấp: POD, tuổi trang bán đa nền tảng, theo dõi, tự quét, nâng cấp CSDL cũ."""
import importlib
import sqlite3
import time
import uuid
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from snakepod import landing, pod


def test_classify_pod_product():
    t, niches, personal = pod.classify("Personalized Dog Mom T-Shirt - Custom Name Hoodie for Mother's Day")
    assert t == "Áo" and {"Chó", "Mẹ"} <= set(niches) and personal
    assert pod.classify("funny-nurse-coffee-mug")[0] == "Cốc / Ly"
    assert pod.classify("Clean your windshield without the hassle") == (None, [], False)


def test_detect_pod_markers():
    assert pod.detect_pod_markers('<script src="https://app.customily.com/x.js"></script> teeinblue') == \
        ["customily", "teeinblue"]


def test_uuid1_timestamp():
    assert abs(landing.uuid1_ts(str(uuid.uuid1())) - time.time()) < 5
    assert landing.uuid1_ts(str(uuid.uuid4())) is None


def test_dates_from_html_priority():
    u = str(uuid.uuid1())
    html_all = ('{"created_at":"2026-09-01T10:00:00+08:00"} {"product_id":"%s"} '
                '<img src="https://cdn.shopify.com/s/files/a.jpg?v=1727740800">' % u)
    ts, src = landing.dates_from_html(html_all)
    assert src == "api" and ts == int(datetime.fromisoformat("2026-09-01T10:00:00+08:00").timestamp())
    assert landing.dates_from_html('{"product_id":"%s"}' % u)[1] == "uuid"
    assert landing.dates_from_html('<img src="//cdn.shopify.com/s/files/a.jpg?v=1727740800">') == (1727740800, "anh")
    assert landing.dates_from_html("<html>nothing</html>") == (None, None)


def test_shoplazza_page_uses_embedded_product_data():
    u = str(uuid.uuid1())
    page = f'<html><title>Dog Mom Tee</title><script src="https://cdn.shoplazza.com/a.js"></script>' \
           f'<script>window.product={{"id":"{u}","price":"24.99"}}</script></html>'

    def handler(req):
        if req.url.path.endswith(".json"):
            return httpx.Response(404, text="not found")
        return httpx.Response(200, text=page)
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        info = landing.check("https://dogmom.store/products/dog-mom-tee", c)
    assert info["platform"] == "shoplazza" and info["date_source"] == "uuid"
    assert abs(info["created_ts"] - time.time()) < 60 and info["price"] == "24.99" and info["title"] == "Dog Mom Tee"


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import analyze, db, demo, jobs, server
    for m in (db, analyze, jobs, demo, server):
        importlib.reload(m)
    return tmp_path


def test_old_database_is_upgraded(app_env):
    from snakepod import config, db
    with sqlite3.connect(config.DB_PATH) as c:   # CSDL kiểu bản cũ: bảng landings chưa có cột mới
        c.execute("CREATE TABLE landings (url TEXT PRIMARY KEY, final_url TEXT, domain TEXT, platform TEXT, "
                  "created_ts INTEGER, published_ts INTEGER, title TEXT, price TEXT, checked_ts INTEGER, error TEXT)")
        c.execute("INSERT INTO landings (url, title) VALUES ('https://a.com/products/x', 'cũ')")
    db.init()
    rows = db.landings_by_url()
    assert rows["https://a.com/products/x"]["title"] == "cũ" and "date_source" in rows["https://a.com/products/x"]


def test_pod_follow_keyword_and_autoscan_api(app_env, monkeypatch):
    from snakepod import db, demo, jobs, server
    demo.main()
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda kind, title, fn: queued.append(title) or True)
    with TestClient(server.app) as c:
        res = c.get("/api/videos", params={"pod": "true"}).json()
        assert res["items"] and all(v["is_pod"] for v in res["items"])
        assert {"name": "Áo", "count": 2} in res["facets"]["product_types"]
        dog = c.get("/api/videos", params={"niche": "Chó"}).json()["items"]
        assert len(dog) == 1 and dog[0]["personalized"]

        niches = c.get("/api/niches").json()
        assert niches[0]["sap_win"] + niches[0]["win"] >= 1

        detail = c.get(f"/api/videos/{dog[0]['cid']}").json()
        assert detail["shop_list"] and detail["page_list"]
        shop = detail["shop_list"][0]["domain"]
        assert c.post("/api/follows", json={"kind": "shop", "key": shop, "name": shop}).status_code == 200
        assert c.post("/api/follows", json={"kind": "bad", "key": "x"}).status_code == 400
        f = next(f for f in c.get("/api/follows").json() if f["key"] == shop)
        assert f["active"] > 0 and f["new_7d"] > 0
        assert any(s["domain"] == shop and s["followed"] for s in c.get("/api/shops").json())
        assert c.get(f"/api/videos/{dog[0]['cid']}").json()["shop_list"][0]["followed"]

        c.post("/api/scan", json={"keyword": "nurse mug", "save": True})
        assert any(k["keyword"] == "nurse mug" for k in c.get("/api/keywords").json())
        assert c.post("/api/autoscan", json={"enabled": True, "hour": 25}).status_code == 400
        assert c.post("/api/autoscan", json={"enabled": True, "hour": 3}).json()["hour"] == 3

        queued.clear()
        assert not jobs.scheduler_tick(datetime(2026, 10, 15, 2, 0))       # chưa tới giờ
        assert jobs.scheduler_tick(datetime(2026, 10, 15, 3, 5))           # tới giờ -> xếp hàng
        assert not jobs.scheduler_tick(datetime(2026, 10, 15, 3, 30))      # hôm nay đã quét rồi
        assert jobs.scheduler_tick(datetime(2026, 10, 16, 3, 1))           # sang ngày mới
        n_kw, n_follow, n_social = len(db.list_watch_keywords()), len(db.list_follows()), len(db.list_social_watch())
        assert n_social and len(queued) == 2 * (n_kw + n_follow + n_social)

        c.delete(f"/api/follows/shop/{shop}")
        assert all(f["key"] != shop for f in c.get("/api/follows").json())
        c.delete("/api/keywords/nurse mug")
        assert all(k["keyword"] != "nurse mug" for k in c.get("/api/keywords").json())


def test_submit_skips_duplicates(app_env):
    from snakepod import jobs
    assert jobs.submit("x", "Quét 'a'", lambda: 0)
    assert not jobs.submit("x", "Quét 'a'", lambda: 0)
