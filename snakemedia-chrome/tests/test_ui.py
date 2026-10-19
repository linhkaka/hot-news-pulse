"""Giao diện (bảng điều khiển + popup), thông báo, chế độ an toàn, lịch tự quét, dữ liệu mẫu."""
import time

VIEWS = ["overview", "sap_win", "win", "scale", "niches", "viral", "spread", "follows", "keywords", "safety", "notify",
         "scan", "all", "theo_doi", "shops", "trang_cu", "cu"]


def _show(page, view):
    page.evaluate("v => setView(v)", view)
    page.wait_for_function("() => !document.querySelector('#content').textContent.includes('Lỗi tải dữ liệu')")
    page.wait_for_timeout(250)


def test_every_view_renders_with_demo_data(ext):
    page = ext.page
    page.reload()
    page.wait_for_selector("text=Xem thử với dữ liệu mẫu")
    page.click("text=Xem thử với dữ liệu mẫu")
    page.wait_for_selector("text=dữ liệu mẫu")
    for view in VIEWS:
        _show(page, view)
        assert "Lỗi" not in page.inner_text("#content"), view
    _show(page, "sap_win")
    assert page.locator(".row").count() == 2
    assert page.locator(".row img").first.get_attribute("src").startswith("data:image/jpeg")
    page.locator(".row").first.click()                       # bảng chi tiết
    page.wait_for_selector("#drawer:not(.hidden) >> text=Vì sao có nhãn này")
    page.click("#drawer .x")
    page.click("text=▦ Lưới")
    page.wait_for_selector(".gcard")
    assert page.locator(".gcard").count() == 2
    _show(page, "viral")
    page.locator(".gcard").first.click()
    page.wait_for_selector("#drawer:not(.hidden) >> text=Số liệu")
    page.select_option("select[data-change=viralSort]", "views")      # bộ lọc dạng select (không dùng onchange)
    page.wait_for_timeout(300)
    assert "Mọi nền tảng" in page.inner_text("#content")
    _show(page, "niches")
    assert "Tưởng niệm" in page.inner_text("#content")
    assert ext.errors == []


def test_popup_shows_counts_and_queues_scan(ext, fake):
    ext.dev(fake.base)
    ext.post("/api/demo")
    popup = ext.open("popup.html")
    popup.wait_for_function("() => document.querySelector('#n-sap').textContent === '2'")
    assert popup.inner_text("#n-win") == "2" and popup.inner_text("#n-viral") == "3"   # 2 đang nổ + 1 viral
    popup.fill("input[name=keyword]", "gadget")
    popup.click("button:has-text('Quét')")
    ext.wait_idle()
    # lượt quét thật đầu tiên tự xoá dữ liệu mẫu
    titles = {v["title"].split()[1] for v in ext.get("/api/videos")["items"]}
    assert titles == {"A", "B"} and ext.get("/api/info")["demo"] is False
    assert ext.call("POST", "/api/demo", ok=False)["status"] == 400        # đã có dữ liệu thật -> không tạo mẫu
    assert ext.errors == []


def test_notify_settings_and_telegram(ext, fake):
    ext.dev(fake.base)
    assert ext.call("POST", "/api/notify/find-chat", ok=False)["detail"] == "Chưa nhập token bot Telegram"
    s = ext.post("/api/notify", {"telegram_token": "123456:SECRET", "desktop": False})
    assert s["has_token"] and s["token_hint"] == "…CRET" and "telegram_token" not in s
    assert ext.post("/api/notify/find-chat")["telegram_chat_id"] == "4242"
    r = ext.post("/api/notify/test")
    assert r["sent"] == ["telegram"] and fake.state["tg"][-1]["chat_id"] == "4242"
    ext.post("/api/notify", {"events": {"viral": False, "bogus": True}})
    ev = ext.get("/api/notify")["events"]
    assert ev == {"sap_win": True, "win": True, "viral": False, "follow": True}
    ext.post("/api/notify", {"telegram_token": ""})
    assert not ext.get("/api/notify")["has_token"]


def test_safety_limits_and_quota(ext):
    assert ext.call("POST", "/api/safety/limits", {"platform": "facebook", "min_gap_s": 5, "max_per_day": 10}, ok=False)["status"] == 400
    ext.post("/api/safety/limits", {"platform": "tiktok", "min_gap_s": 60, "max_per_day": 2})
    tt = [p for p in ext.get("/api/safety")["platforms"] if p["key"] == "tiktok"][0]
    assert tt["min_gap_s"] == 60 and tt["max_per_day"] == 2
    # đồng hồ giả: lần 2 phải nghỉ đủ 60 giây, lần 3 hết lượt trong ngày
    r = ext.js("""async () => {
      let t = Date.now() / 1000; const slept = []; const logs = [];
      const now = () => t, sleep = async ms => { slept.push(ms); t += ms / 1000; };
      await SP.safety.beforeScan('tiktok', m => logs.push(m), () => false, sleep, now);
      await SP.safety.beforeScan('tiktok', m => logs.push(m), () => false, sleep, now);
      let third = null;
      try { await SP.safety.beforeScan('tiktok', m => logs.push(m), () => false, sleep, now); } catch (e) { third = e.message; }
      return {waited: slept.reduce((s, x) => s + x, 0), logs, third};
    }""")
    assert 59_000 <= r["waited"] <= 60_000 and r["logs"][0].startswith(("Nghỉ 59 giây", "Nghỉ 60 giây"))
    assert r["third"].startswith("Đã quét TikTok 2/2 lần hôm nay")


def test_autoscan_schedule(ext):
    ext.js("async () => { await SP.db.addWatchKeyword('dog mom shirt', 'US'); await SP.db.addFollow('shop', 'a.com', 'a.com'); }")
    assert ext.call("POST", "/api/autoscan", {"enabled": True, "hour": 30}, ok=False)["status"] == 400
    a = ext.post("/api/autoscan", {"enabled": True, "hour": 3})
    assert a["hour"] == 3 and a["keywords"] == 1 and a["follows"] == 1
    r = ext.js("""async () => {
      const at = (d, h, m) => new Date(2026, 9, d, h, m);
      const out = [await SP.jobs.schedulerTick(at(15, 2, 0)), await SP.jobs.schedulerTick(at(15, 3, 5)),
                   await SP.jobs.schedulerTick(at(15, 3, 30)), await SP.jobs.schedulerTick(at(16, 3, 1))];
      return out;
    }""")
    assert r == [False, True, False, True]
    assert ext.get("/api/autoscan")["last_date"] == "2026-10-16"


def test_dashboard_buttons_without_inline_scripts(ext):
    """Trang tiện ích cấm onclick="..." -> mọi nút dùng data-act / data-change."""
    page = ext.page
    ext.post("/api/demo")
    for view in VIEWS:
        _show(page, view)
        assert page.locator("[onclick], [onchange]").count() == 0, view
    _show(page, "overview")
    page.click("a.card:has-text('Video Win')")
    page.wait_for_timeout(300)
    assert page.evaluate("location.hash") == "#win"
    _show(page, "scan")
    page.click(".chip:has-text('nurse shirt')")
    assert page.input_value("#scanForm [name=keyword]") == "nurse shirt"
    page.uncheck("[data-change=passive]")
    page.wait_for_timeout(300)
    assert ext.get("/api/passive") == {"enabled": False}
    assert ext.errors == []



def test_web_pages_cannot_control_the_extension(ext, fake):
    """Lệnh API gửi từ trong 1 trang web (như content script trên Facebook) bị từ chối."""
    ext.dev(fake.base)
    page = ext.ctx.new_page()
    page.goto(fake.base + "/topads")
    r = ext.js("""async url => {
      const [tab] = await chrome.tabs.query({url: url + '/*'});
      const [res] = await chrome.scripting.executeScript({target: {tabId: tab.id},
        func: () => chrome.runtime.sendMessage({type: 'api', method: 'POST', path: '/api/demo'})});
      return res.result;
    }""", fake.base)
    assert r == {"ok": False, "status": 403, "detail": "Forbidden"}
    assert ext.get("/api/info")["has_data"] is False
