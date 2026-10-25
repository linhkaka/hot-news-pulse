"""Bản nâng cấp trong tiện ích: giao diện dùng chung với app, Video Tiềm Năng / SP bò sữa / Video test / Đã ẩn,
lịch sử theo dõi, Đào sâu hàng loạt, Quét store win, quét hàng loạt, góp kho (dùng chung file với bản app)."""
import importlib
import re

from conftest import EXT

STATIC = EXT.parent / "snakemedia-pod" / "snakepod" / "static"


def test_ui_matches_app():
    """Giao diện là 1 file dùng chung: sửa ở app rồi chạy sync_ui.py."""
    for src, dst in {"app.js": "dashboard.js", "style.css": "style.css", "logo.png": "logo.png"}.items():
        assert (STATIC / src).read_bytes() == (EXT / dst).read_bytes(), f"chạy python snakemedia-chrome/sync_ui.py ({dst})"
    nav = lambda p: re.search(r'<nav id="nav">.*?</nav>', p.read_text(), re.S).group(0)
    assert nav(STATIC / "index.html") == nav(EXT / "dashboard.html")


def test_new_tabs_marks_and_detail(ext):
    ext.post("/api/demo")
    s = ext.get("/api/stats")
    assert s["tabs"]["cow"] == 1 and s["tabs"]["potential"] >= 1 and s["tabs"]["test"] == 1 and s["tabs"]["dig"] >= 2
    [cow] = ext.get("/api/videos?tab=cow")["items"]
    assert cow["title"].startswith("Grandma's Garden Flag") and cow["delta"]["pages_active"] > 0 and cow["thumb_src"]
    assert any("Veteran" in v["title"] for v in ext.get("/api/videos?tab=potential")["items"])
    assert [v["marks"] for v in ext.get("/api/videos?tab=test")["items"]] == [["test"]]

    ext.post("/api/marks", {"cid": cow["cid"], "kind": "hidden"})
    assert all(v["cid"] != cow["cid"] for v in ext.get("/api/videos?limit=200")["items"])
    assert [v["cid"] for v in ext.get("/api/videos?tab=hidden")["items"]] == [cow["cid"]]
    assert ext.get("/api/stats")["tabs"]["cow"] == 0
    ext.post("/api/marks", {"cid": cow["cid"], "kind": "hidden", "on": False})
    assert ext.call("POST", "/api/marks", {"cid": "x", "kind": "bad"}, ok=False)["status"] == 400

    d = ext.get(f"/api/videos/{cow['cid']}")
    assert len(d["history"]) == 3 and d["history"][0]["day"] > d["history"][-1]["day"]
    assert d["compare_price"] == "49.98" and d["sell_pages"][0]["ads"] >= 1 and d["urls_total"] == 3
    amazon = next(x["url"] for x in d["sourcing"] if x["name"] == "Amazon")
    assert amazon.startswith("https://www.amazon.com/s?k=") and "Grandma" in amazon
    assert [c["ok"] for c in d["flag_checks"]] == [False, True]

    st = ext.get("/api/stores")
    assert st["summary"]["pending"] == st["total"] > 0 and "flagcraft.co" in {r["domain"] for r in st["items"]}
    assert next(r for r in st["items"] if r["domain"] == "bloomyard.com")["tabs"][0] == "Theo dõi"
    assert ext.get("/api/keywords/suggest")


def test_dashboard_new_views(ext):
    page = ext.page
    ext.post("/api/demo")
    for view in ["stores", "dig", "potential", "cow", "test", "hidden", "history", "data", "scan", "keywords"]:
        page.evaluate("v => setView(v)", view)
        page.wait_for_timeout(350)
        assert "Lỗi" not in page.inner_text("#content"), view
    page.evaluate("v => setView(v)", "cow")
    page.wait_for_selector("tr.vrow")                         # SP bò sữa mặc định dạng bảng
    page.locator("tr.vrow").first.click()
    page.wait_for_selector("#drawer:not(.hidden) >> text=Lịch sử theo dõi")
    page.click("#drawer >> text=+ Video test")
    page.wait_for_selector("#drawer >> text=✓ Đang test")
    assert ext.get("/api/stats")["tabs"]["test"] == 2
    page.evaluate("v => setView(v)", "scan")
    page.wait_for_selector("#batchForm")
    page.click("#kwBox >> text=Tự đào")                       # gợi ý từ khoá tự đào từ video hot trong kho
    page.wait_for_selector("#kwBox .kwpick")
    assert page.locator("#kwBox .kwpick").first.get_attribute("value")
    assert ext.errors == []


def test_batch_scan_store_sweep_and_dig(ext, fake):
    ext.dev(fake.base)
    r = ext.post("/api/scan", {"keywords": ["gadget", " ", "gadget"], "max_ads": 50})
    assert r["queued"] == 1
    ext.wait_idle()
    shop = f"127.0.0.1:{fake.port}"
    st = ext.get("/api/stores")
    assert {x["domain"] for x in st["items"]} == {shop, f"localhost:{fake.port}"}
    fake.state["page"] = 0
    assert ext.post("/api/stores/sweep", {"domains": [shop]})["queued"] == 1
    ext.wait_idle()
    done = ext.get("/api/stores?status=done")["items"]
    assert [x["domain"] for x in done] == [shop] and done[0]["ads_found"] == 3 and done[0]["new_videos"] == 0
    assert ext.get("/api/scans")[0]["target"] == f"Soi store {shop}"
    # đào sâu: video Sắp WIN chưa đào -> đào -> hết trong danh sách chờ
    cands = ext.get("/api/videos?tab=dig")["items"]
    assert [v["label"] for v in cands] == ["sap_win"]
    fake.state["page"] = 0
    assert ext.post("/api/dig/batch", {"n": 5})["queued"] == 1
    ext.wait_idle()
    assert ext.get("/api/videos?tab=dig")["items"] == []
    assert ext.get(f"/api/videos/{cands[0]['cid']}")["dug_ts"]


def test_export_import_shares_data_with_the_app(ext, fake, tmp_path, monkeypatch):
    ext.dev(fake.base)
    ext.post("/api/scan", {"keyword": "gadget", "max_ads": 50})
    ext.wait_idle()
    data = ext.get("/api/export")
    assert data["format"] == "snakemedia-pod" and len(data["ads"]) == 5
    before = sorted((v["label"], v["ads_total"]) for v in ext.get("/api/videos")["items"])

    # bản app nhập file của tiện ích ...
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path / "app"))
    from snakepod import config
    importlib.reload(config)
    from snakepod import analyze, db
    importlib.reload(db)
    db.init()
    assert db.import_data(data) == (5, len(data["landings"]))
    videos = analyze.build_videos(db.all_ads(), db.landings_by_url())
    assert sorted((v["label"], v["ads_total"]) for v in videos) == before

    # ... và tiện ích nhập file của bản app (xoá sạch rồi nhập lại)
    ext.js("SP.db.wipeAll()")
    r = ext.post("/api/import", db.export_data())
    assert r == {"ads": 5, "landings": len(data["landings"])}
    ext.wait_idle()
    assert sorted((v["label"], v["ads_total"]) for v in ext.get("/api/videos")["items"]) == before
    assert ext.post("/api/import", db.export_data()) == {"ads": 0, "landings": 0}
    assert ext.call("POST", "/api/import", {"ads": []}, ok=False)["status"] == 400


def test_history_follows_video_when_cluster_grows(ext):
    r = ext.js("""async () => {
      const v = (cid, ids, shops) => ({cid, ads: ids.map(ad_id => ({ad_id})), pages_active: 1, shops_active: shops, shops_win: 0,
        buckets: {scale: 0}, ads_active: 1, urls_total: 1});
      await SP.db.recordHistory([v('5', ['5'], 1)], '2026-10-18');
      await SP.db.setMark('5', 'test', true);
      await SP.db.markDug('5');
      await SP.db.rekey([v('1', ['1', '5'], 2)]);
      await SP.db.recordHistory([v('1', ['1', '5'], 2)], '2026-10-19');
      const h = await SP.db.history(['1', '5']);
      return {h1: h['1'].map(x => [x.day, x.shops_active]), h5: h['5'].length,
              marks: Object.keys(await SP.db.marks()), digs: Object.keys(await SP.db.digs())};
    }""")
    assert r == {"h1": [["2026-10-19", 2], ["2026-10-18", 1]], "h5": 0, "marks": ["1"], "digs": ["1"]}
