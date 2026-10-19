"""Bản nâng cấp: Video Tiềm Năng, SP bò sữa, lịch sử theo dõi, đang bán ở N trang + giá gạch, Video test / Đã ẩn,
Đào sâu hàng loạt, Quét store win, quét hàng loạt + tự đào từ khoá, tìm nguồn hàng, góp kho (xuất / nhập)."""
import importlib
import time

import pytest
from fastapi.testclient import TestClient

from snakepod import analyze, landing

NOW = 1_760_000_000
DAY = 86400


def ad(i, domain, age, active=True, page=None, link=None, dhash="aaaaaaaaaaaaaaaa"):
    return {"ad_id": str(i), "domain": domain, "page_id": page or f"p{i}", "start_ts": NOW - age * DAY, "is_active": int(active),
            "collation_count": 1, "dhash": dhash, "link_url": link or f"https://{domain}/products/p", "body": "x",
            "collation_id": None, "page_name": None, "end_ts": None, "title": None, "thumb_url": None, "video_url": None}


def test_potential_and_cash_cow_flags():
    # 1 shop, 2 page, video 3 ngày -> chưa Sắp WIN nhưng là Tiềm năng
    v = analyze.summarize("c", [ad(1, "a.com", 3, page="p1"), ad(2, "a.com", 2, page="p2")], {}, now=NOW)
    assert v["label"] == "theo_doi" and v["potential"] and not v["cash_cow"]
    assert v["flag_checks"][0]["ok"] is True
    # Sắp WIN thì không còn là Tiềm năng
    v = analyze.summarize("c", [ad(1, "a.com", 3), ad(2, "b.com", 2)], {}, now=NOW)
    assert v["label"] == "sap_win" and not v["potential"]
    # chạy đều nhiều tuần, 3 shop, nhiều QC sống > 14 ngày -> Bò sữa (nhãn chính vẫn là Video già)
    cow = [ad(i, d, age) for i, (d, age) in enumerate([("a.com", 60), ("a.com", 40), ("b.com", 30), ("b.com", 20),
                                                       ("c.com", 25), ("c.com", 3)])]
    v = analyze.summarize("c", cow, {}, now=NOW)
    assert v["cash_cow"] and v["label"] == "cu" and v["longest_run_days"] == 60 and v["buckets"]["old"] == 5
    v = analyze.summarize("c", cow[:3], {}, now=NOW)            # chỉ 2 shop -> chưa phải bò sữa
    assert not v["cash_cow"] and v["flag_checks"][1]["ok"] is False


def test_sell_pages_and_compare_price():
    lands = {"https://a.com/products/p": {"created_ts": NOW - 5 * DAY, "price": "21.99", "compare_price": "42.99",
                                          "platform": "shopify"}}
    v = analyze.summarize("c", [ad(1, "a.com", 3), ad(2, "a.com", 2), ad(3, "www.b.com", 1, link="https://www.b.com/products/q")],
                          lands, now=NOW)
    assert v["price"] == "21.99" and v["compare_price"] == "42.99" and v["urls_total"] == 2
    assert [p["domain"] for p in v["sell_pages"]] == ["a.com", "b.com"] and v["sell_pages"][0]["ads"] == 2
    assert landing.parse_shopify_product({"product": {"variants": [{"price": "9", "compare_at_price": "19"}]}})["compare_price"] == "19"


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import analyze as an, db, demo, jobs, server
    for m in (db, an, jobs, demo, server):
        importlib.reload(m)
    return tmp_path


def test_history_follows_video_when_cluster_grows(app_env):
    from snakepod import db, jobs
    db.init()
    db.upsert_ads([{**ad(5, "a.com", 3)}])
    jobs.recompute()
    [v] = db.list_videos()
    assert v["cid"] == "5" and db.history(["5"])["5"][0]["shops_active"] == 1
    db.set_mark("5", "test", True)
    db.mark_dug("5")
    # QC mới (mã nhỏ hơn) cùng video từ shop khác -> mã video đổi thành "1", lịch sử/đánh dấu đi theo
    db.upsert_ads([{**ad(1, "b.com", 2)}])
    db.set_thumb("1", None, "aaaaaaaaaaaaaaaa")
    db.set_thumb("5", None, "aaaaaaaaaaaaaaaa")
    jobs.recompute()
    [v] = db.list_videos()
    assert v["cid"] == "1"
    h = db.history(["1", "5"])
    assert h["5"] == [] and h["1"][0]["shops_active"] == 2 and len(h["1"]) == 1     # cùng ngày -> ghi đè
    assert db.marks() == {"1": {"test"}} and set(db.digs()) == {"1"}


def test_tabs_marks_dig_and_stores_api(app_env, monkeypatch):
    from snakepod import db, demo, jobs, server
    demo.main()
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda kind, title, fn: queued.append(title) or True)
    with TestClient(server.app) as c:
        s = c.get("/api/stats").json()
        assert s["tabs"]["cow"] == 1 and s["tabs"]["potential"] >= 1 and s["tabs"]["test"] == 1 and s["tabs"]["dig"] >= 2
        cow = c.get("/api/videos", params={"tab": "cow"}).json()["items"]
        assert [v["title"][:20] for v in cow] == ["Grandma's Garden Fla"] and cow[0]["delta"]["pages_active"] > 0
        pot = c.get("/api/videos", params={"tab": "potential"}).json()["items"]
        assert all(v["potential"] for v in pot) and any("Veteran" in v["title"] for v in pot)
        test = c.get("/api/videos", params={"tab": "test"}).json()["items"]
        assert len(test) == 1 and test[0]["marks"] == ["test"]

        # ẩn 1 video: biến mất khỏi danh sách, hiện ở Đã ẩn
        cid = cow[0]["cid"]
        assert c.post("/api/marks", json={"cid": cid, "kind": "bad"}).status_code == 400
        c.post("/api/marks", json={"cid": cid, "kind": "hidden"})
        assert all(v["cid"] != cid for v in c.get("/api/videos", params={"limit": 200}).json()["items"])
        assert [v["cid"] for v in c.get("/api/videos", params={"tab": "hidden"}).json()["items"]] == [cid]
        c.post("/api/marks", json={"cid": cid, "kind": "hidden", "on": False})

        d = c.get(f"/api/videos/{cid}").json()
        assert len(d["history"]) == 3 and d["history"][0]["day"] > d["history"][-1]["day"]
        assert d["compare_price"] and d["sell_pages"] and {"AliExpress", "Amazon"} <= {x["name"] for x in d["sourcing"]}
        assert "grandma" in next(x["url"] for x in d["sourcing"] if x["name"] == "Amazon").lower()

        # Đào sâu hàng loạt
        n_dig = len(jobs.dig_candidates())
        assert c.post("/api/dig/batch", json={"n": 2}).json()["queued"] == 2 and len(queued) == 2
        db.mark_dug(jobs.dig_candidates()[0]["cid"])
        assert len(jobs.dig_candidates()) == n_dig - 1

        # Quét store win: shop của video hot, chưa soi
        st = c.get("/api/stores").json()
        assert st["summary"]["pending"] == st["total"] > 0 and st["items"][0]["tabs"]
        assert "bloomyard.com" in {r["domain"] for r in st["items"]}                   # đang theo dõi
        queued.clear()
        assert c.post("/api/stores/sweep", json={"n": 3}).json()["queued"] == 3
        assert all(t.startswith("Soi store ") for t in queued)
        db.save_store_sweep(st["items"][0]["domain"], 12, 2)
        st2 = c.get("/api/stores", params={"status": "done"}).json()
        assert st2["total"] == 1 and st2["items"][0]["new_videos"] == 2 and st2["summary"]["new_videos_7d"] == 2

        # quét hàng loạt + gợi ý từ khoá
        queued.clear()
        r = c.post("/api/scan", json={"keywords": ["a mug", " ", "b shirt", "a mug"], "save": True}).json()
        assert r["queued"] == 2 and queued == ["Quét 'a mug'", "Quét 'b shirt'"]
        sug = c.get("/api/keywords/suggest").json()
        assert sug and all(s["keyword"] not in ("demo", "a mug") for s in sug)
        assert c.post("/api/autoscan", json={"enabled": True, "hour": 1, "stores": 500}).status_code == 400
        assert c.post("/api/autoscan", json={"enabled": True, "hour": 1, "stores": 5}).json()["stores"] == 5


def land(url, checked, price):
    return {"url": url, "final_url": url, "domain": None, "platform": None, "created_ts": NOW, "published_ts": None,
            "title": None, "price": price, "checked_ts": checked, "error": None}


def test_export_import_merges_two_stores(app_env, tmp_path, monkeypatch):
    from snakepod import config, db
    db.init()
    db.upsert_ads([{**ad(1, "a.com", 10)}, {**ad(2, "b.com", 3)}])
    db.save_landing(land("https://a.com/products/p", 100, "9"))
    data = db.export_data()
    assert data["format"] == "snakemedia-pod" and len(data["ads"]) == 2

    # máy đồng đội: có QC 1 nhưng thấy muộn hơn, chưa có QC 2
    other = tmp_path / "other"
    monkeypatch.setattr(config, "DATA_DIR", other)
    monkeypatch.setattr(config, "DB_PATH", other / "snakepod.db")
    db.init()
    db.upsert_ads([{**ad(1, "a.com", 4)}])
    db.save_landing(land("https://a.com/products/p", 50, "7"))
    assert db.import_data(data) == (1, 1)
    ads = {a["ad_id"]: a for a in db.all_ads()}
    assert set(ads) == {"1", "2"} and ads["1"]["start_ts"] == NOW - 10 * DAY        # lấy mốc sớm nhất
    assert db.landings_by_url()["https://a.com/products/p"]["price"] == "9"           # bản đọc mới hơn
    assert db.import_data(data) == (0, 0)                                              # nhập lại không nhân đôi
    with pytest.raises(ValueError):
        db.import_data({"ads": []})


from tests.test_e2e import _chromium, fake_facebook  # noqa: E402,F401


@pytest.mark.skipif(_chromium() is None, reason="không có Chromium")
def test_store_sweep_against_fake_ad_library(app_env, monkeypatch, fake_facebook):
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
    monkeypatch.setitem(safety.DEFAULT_LIMITS, "facebook", {"min_gap_s": 0, "max_per_day": 100})
    monkeypatch.setattr(scraper, "BASE", f"http://127.0.0.1:{fake_facebook.port}/ads/library/")
    db.init()
    shop = f"127.0.0.1:{fake_facebook.port}"
    assert jobs.sweep_job(shop, "US")() == 3                  # chỉ giữ QC của đúng shop đó
    row = db.store_sweeps()[shop]
    assert row["ads_found"] == 3 and row["new_videos"] == 2 and row["swept_ts"] >= int(time.time()) - 60
