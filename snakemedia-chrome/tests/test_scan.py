"""Quét thật bằng tiện ích (cửa sổ Chrome + cuộn + bắt phản hồi mạng + tải ảnh + đọc trang bán + chấm nhãn)
trên các trang Facebook / TikTok / Creative Center GIẢ chạy trên máy."""
import base64
import io
import json
import time
import zipfile


def test_keyword_scan_full_flow(ext, fake):
    ext.dev(fake.base)
    ext.post("/api/scan", {"keyword": "gadget", "country": "US", "max_ads": 50, "save": True})
    ext.wait_idle()

    [scan] = ext.get("/api/scans")
    assert scan["status"] == "xong" and scan["n_ads"] == 5, scan
    videos = {v["title"].split()[1]: v for v in ext.get("/api/videos?limit=200")["items"]}
    assert set(videos) == {"A", "B"}, videos.keys()
    a, b = videos["A"], videos["B"]
    assert round(a["video_age_days"]) == 12              # tính cả QC đã tắt
    assert a["ads_gone"] == 1 and a["shops_win"] == 2 and a["label"] == "win"
    assert a["price"] == "19.99" and a["platform"] == "shopify" and round(a["landing_age_days"]) == 12
    assert b["shops_active"] == 2 and b["label"] == "sap_win"
    assert a["thumb_src"].startswith("data:image/jpeg;base64,")      # ảnh lưu trong tiện ích
    detail = ext.get(f"/api/videos/{a['cid']}")
    assert len(detail["ads"]) == 3 and {s["domain"] for s in detail["shop_list"]} == {f"127.0.0.1:{fake.port}", f"localhost:{fake.port}"}
    assert [k["keyword"] for k in ext.get("/api/keywords")] == ["gadget"]
    assert ext.get("/api/keywords")[0]["last_scan_ts"]
    # cửa sổ quét đã đóng
    assert all("ads/library" not in p.url for p in ext.ctx.pages)


def test_checkpoint_stops_and_blocks_facebook(ext, fake):
    ext.dev(fake.base)
    ext.post("/api/scan", {"keyword": "checkpoint", "max_ads": 50})
    ext.wait_idle()
    [scan] = ext.get("/api/scans")
    assert scan["status"] == "checkpoint" and "checkpoint" in scan["error"]
    blocked = ext.get("/api/jobs")["blocked"]
    assert "facebook" in blocked and "tiktok" not in blocked
    # đang tạm dừng -> lượt sau bị bỏ qua, không mở Facebook
    ext.post("/api/scan", {"keyword": "gadget", "max_ads": 50})
    ext.wait_idle()
    assert ext.get("/api/scans")[0]["status"] == "bo qua"
    # gói chẩn đoán đã lưu và tải được
    [bundle] = ext.get("/api/diag")
    assert "checkpoint" in bundle["error"].lower() and "/checkpoint/" in bundle["final_url"]
    z = ext.get(f"/api/diag/{bundle['name']}/download")
    names = zipfile.ZipFile(io.BytesIO(base64.b64decode(z["base64"]))).namelist()
    assert f"{bundle['name']}/meta.json" in names and f"{bundle['name']}/page.html" in names
    ext.post("/api/safety/resume/facebook")
    assert "facebook" not in ext.get("/api/jobs")["blocked"]


def test_zero_results_saves_diag_bundle(ext, fake):
    ext.dev(fake.base)
    fake.state["empty"] = True
    ext.post("/api/scan", {"keyword": "nothing", "max_ads": 50})
    ext.wait_idle()
    assert ext.get("/api/scans")[0]["n_ads"] == 0
    [bundle] = ext.get("/api/diag")
    assert bundle["error"] == "Không đọc được kết quả nào" and bundle["responses"] >= 1
    z = zipfile.ZipFile(io.BytesIO(base64.b64decode(ext.get(f"/api/diag/{bundle['name']}/download")["base64"])))
    meta = json.loads(z.read(f"{bundle['name']}/meta.json"))
    assert meta["items"] == 0 and "graphql" in z.read(f"{bundle['name']}/responses.jsonl").decode()


def test_tiktok_and_topads_scans(ext, fake):
    ext.dev(fake.base)
    ext.post("/api/viral/scan", {"platform": "tiktok", "keyword": "dog mom shirt", "save": True})
    ext.post("/api/viral/scan", {"platform": "tiktok_ads", "keyword": "mug"})
    ext.wait_idle()
    assert fake.state["typed"] == "mug"                     # đã gõ từ khoá vào ô tìm kiếm Top Ads
    res = ext.get("/api/viral?limit=200")
    items = {v["vid"]: v for v in res["items"]}
    assert set(items) == {"tiktok:1", "tiktok:2", "tiktok:3", "tiktok_ads:ad1", "tiktok_ads:ad2"}
    assert all(v["cover_src"] for v in items.values())       # ảnh bìa đã tải về
    assert items["tiktok:1"]["label"] == "viral" and items["tiktok:2"]["label"] == "dang_len"
    assert items["tiktok:3"]["label"] == "binh_thuong" and items["tiktok_ads:ad2"]["label"] == "top_ads"
    assert [(k["platform"], k["keyword"]) for k in ext.get("/api/viral/keywords")] == [("tiktok", "dog mom shirt")]
    detail = ext.get("/api/viral/tiktok:1")
    assert len(detail["snapshots"]) == 1 and detail["checks"]


def test_passive_capture_while_browsing(ext, fake):
    """Bạn tự mở Thư viện QC: tiện ích tự lưu QC trong trang + QC tải thêm khi cuộn."""
    ext.dev(fake.base)
    page = ext.ctx.new_page()
    page.goto(fake.base + "/ads/library/?q=gadget")
    page.wait_for_timeout(1000)
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(1500)
    page.close()
    ext.wait_idle()
    deadline = time.time() + 30
    while time.time() < deadline and ext.get("/api/stats")["total"] < 2:
        time.sleep(0.5)
    assert ext.get("/api/stats")["total"] == 2               # video A và B
    assert ext.js("SP.db.count('ads')") == 4                 # 2 QC trong trang + 2 QC khi cuộn
    assert ext.get("/api/scans")[0]["target"] == "Lưu QC/video vừa lướt"
    assert ext.js("SP.db.countRateEvents('facebook', 0)") == 0     # không tính vào giới hạn quét
    # tắt tự lưu -> không lưu nữa
    ext.post("/api/passive", {"enabled": False})
    assert ext.get("/api/passive") == {"enabled": False}


def test_follow_shop_notifies_new_ads(ext, fake):
    ext.dev(fake.base)
    shop = f"127.0.0.1:{fake.port}"
    ext.post("/api/notify", {"telegram_token": "123:abc", "telegram_chat_id": "42", "desktop": False})
    ext.post("/api/follows", {"kind": "shop", "key": shop, "name": "Shop 1"})
    ext.post(f"/api/follows/shop/{shop}/scan")
    ext.wait_idle()
    [f] = ext.get("/api/follows")
    assert f["ads"] == 3 and f["active"] == 2 and f["last_scan_ts"]
    texts = [m["text"] for m in fake.state["tg"]]
    assert texts == ["<b>★ Shop 1 vừa lên 3 QC mới</b>\nMở mục Theo dõi đặc biệt để xem."], texts
    # quét đủ mọi shop -> video A thành Win, B thành Sắp WIN -> mỗi loại báo 1 lần
    fake.state["page"] = 0
    ext.post("/api/scan", {"keyword": "gadget", "max_ads": 50})
    ext.wait_idle()
    texts = [m["text"] for m in fake.state["tg"]][1:]
    assert len(texts) == 2 and "Sắp WIN mới (1)" in texts[0] and "Video Win mới (1)" in texts[1], texts
    assert "Video B amazing gadget" in texts[0] and "12.0 ngày" in texts[1]
    ext.post("/api/recompute")
    ext.wait_idle()
    assert len(fake.state["tg"]) == 3                    # chấm lại không báo trùng
