"""Bản final 2.0: các lỗi tìm được khi soát toàn bộ code — mỗi bài kiểm thử giữ 1 lỗi không quay lại."""
import importlib
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

NOW = 1_760_000_000


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import analyze, db, demo, jobs, server, shopify
    for m in (db, analyze, jobs, shopify, demo, server):
        importlib.reload(m)
    db.init()
    return tmp_path


def _ad(i, dhash=None, **kw):
    return {"ad_id": i, "collation_id": None, "collation_count": 1, "page_id": "p" + i, "page_name": "P", "start_ts": NOW,
            "end_ts": None, "is_active": 1, "title": None, "body": "Dog shirt " + i, "link_url": f"https://s{i}.com/products/x",
            "domain": f"s{i}.com", "thumb_url": None, "video_url": None, "dhash": dhash, "keyword": None,
            "first_seen": NOW, "last_seen": NOW, **kw}


def test_import_rejects_unsafe_ids_urls_and_bad_hashes(app_env):
    from snakepod import db, jobs
    data = {"format": "snakemedia-pod", "version": 1, "landings": [{"url": "file:///etc/passwd", "checked_ts": 1}], "ads": [
        _ad("../../evil", thumb_url="http://x/a.jpg"), _ad("C:\\Windows\\x"), _ad("5", dhash="zzzz", thumb_url="javascript:alert(1)"),
        _ad("6", dhash="aaaaaaaaaaaaaaaa")]}
    assert db.import_data(data) == (2, 0)
    rows = {a["ad_id"]: a for a in db.all_ads()}
    assert set(rows) == {"5", "6"} and rows["5"]["dhash"] is None and rows["5"]["thumb_url"] is None
    db.upsert_ads([_ad("7", thumb_url="http://x/b.jpg")])
    with sqlite3.connect(db.config.DB_PATH) as c:                        # dữ liệu cũ có sẵn mã ảnh hỏng
        c.execute("UPDATE ads SET dhash='not-hex!' WHERE ad_id='7'")
    jobs.recompute()                                                     # không còn hỏng cả lượt chấm lại
    assert len(db.list_videos()) == 3


def test_api_refuses_other_sites(app_env, monkeypatch):
    from snakepod import server
    with TestClient(server.app, base_url="http://127.0.0.1:8765") as c:
        assert c.get("/api/stats").status_code == 200
        assert c.post("/api/stop", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
        assert c.post("/api/stop", headers={"Origin": "https://evil.example"}).status_code == 403
        assert c.post("/api/safety/resume/facebook", headers={"Origin": "null"}).status_code == 403
        assert c.get("/api/export", headers={"Host": "attacker.example:8765"}).status_code == 403
    monkeypatch.delenv("SNAKEPOD_TEST")
    with TestClient(server.app) as c:                                   # tên máy lạ (kể cả "testserver") bị chặn
        assert c.get("/api/stats").status_code == 403


def test_keywords_with_slash_can_be_removed(app_env):
    from snakepod import db, server
    db.add_watch_keyword("24/7 nurse shirt", "US")
    db.add_social_watch("tiktok", "mom/dad", "")
    with TestClient(server.app) as c:
        assert c.delete("/api/keywords/24%2F7%20nurse%20shirt").status_code == 200
        assert c.delete("/api/viral/keywords/tiktok/mom%2Fdad", params={"country": ""}).status_code == 200
    assert db.list_watch_keywords() == [] and db.list_social_watch() == []


def test_new_video_id_keeps_notified_and_clone(app_env, monkeypatch):
    from snakepod import db, notify
    v = lambda cid, ids: {"cid": cid, "ads": [{"ad_id": x} for x in ids], "label": "sap_win"}
    db.mark_notified("sap_win", ["5000"])
    db.set_setting("clones", {"5000": {"admin_url": "u"}})
    db.rekey([v("40000", ["40000", "5000"])])
    assert db.unseen_notified("sap_win", ["40000"]) == [] and db.get_setting("clones") == {"40000": {"admin_url": "u"}}


def test_worker_survives_database_errors(app_env, monkeypatch):
    from snakepod import db, jobs
    jobs.SESSION.clear()
    jobs.start_worker()
    calls = []
    real = db.start_scan

    def flaky(kind, title):
        calls.append(title)
        if len(calls) == 1:
            raise sqlite3.OperationalError("database is locked")
        return real(kind, title)
    monkeypatch.setattr(db, "start_scan", flaky)
    jobs.submit("x", "Việc 1", lambda: 1)
    jobs.submit("x", "Việc 2", lambda: 2)
    for _ in range(50):
        if len(jobs.SESSION) == 2:
            break
        time.sleep(0.1)
    assert [(d["title"], d["status"]) for d in jobs.SESSION] == [("Việc 1", "loi"), ("Việc 2", "xong")]
    assert jobs.status()["current"] is None and jobs.submit("x", "Việc 1", lambda: 0)   # xếp lại được


def test_follow_shop_link_is_normalised(app_env):
    from snakepod import db, server
    with TestClient(server.app) as c:
        c.post("/api/follows", json={"kind": "shop", "key": " https://www.Bloomyard.com/products/x?y=1 "})
        assert c.post("/api/follows", json={"kind": "shop", "key": "https://"}).status_code == 400
    assert [(f["key"], f["name"]) for f in db.list_follows()] == [("bloomyard.com", "bloomyard.com")]


def test_old_watch_country_fixed_for_non_market_sources(app_env):
    from snakepod import db
    with sqlite3.connect(db.config.DB_PATH) as c:
        c.executemany("INSERT INTO social_watch VALUES (?, ?, ?, 1, NULL)",
                      [("tiktok", "dog", "US"), ("tiktok", "dog", ""), ("fb_reels", "mug", "GB"), ("tiktok_ads", "", "US")])
    db.init()
    assert sorted((w["platform"], w["keyword"], w["country"]) for w in db.list_social_watch()) == [
        ("fb_reels", "mug", ""), ("tiktok", "dog", ""), ("tiktok_ads", "", "US")]
