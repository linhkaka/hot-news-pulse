"""Bản final 2.0 (tiện ích): các lỗi tìm được khi soát toàn bộ code — mỗi bài kiểm thử giữ 1 lỗi không quay lại."""
import html
import json

from snakepod import kwtrends, shopify


def test_demo_is_cleared_before_real_data_is_saved(ext, fake):
    ext.post("/api/demo")
    ext.dev(fake.base)
    ext.post("/api/scan", {"keyword": "gadget", "max_ads": 50, "save": True})
    ext.wait_idle()
    assert [w["keyword"] for w in ext.get("/api/keywords")] == ["gadget"]          # không bị xoá cùng dữ liệu mẫu
    assert ext.get("/api/info")["demo"] is False
    assert all(not v["cid"].startswith("demo") for v in ext.get("/api/videos")["items"])


def test_interrupted_job_runs_again_and_scan_window_is_closed(ext):
    r = ext.js("""async () => {
      const w = await chrome.windows.create({url: "about:blank", type: "normal"});
      await chrome.storage.local.set({scanWindows: [w.id], jobs: {current: "Chấm lại", pending: [],
        job: {kind: "recompute", title: "Chấm lại", args: {}}, log: []}});
      await SP.db.startScan("keyword", "Quét 'x'");
      await SP.jobs.restore();
      for (let i = 0; i < 50 && SP.jobs.isBusy(); i++) await new Promise(r => setTimeout(r, 100));
      const wins = (await chrome.windows.getAll()).map(x => x.id);
      return {open: wins.includes(w.id), scans: (await SP.db.listScans()).map(s => [s.target, s.status]),
              left: (await chrome.storage.local.get("scanWindows")).scanWindows};
    }""")
    assert r["open"] is False and r["left"] == []
    assert ["Quét 'x'", "gian doan"] in r["scans"] and ["Chấm lại", "xong"] in r["scans"]
    log = [x["msg"] for x in ext.get("/api/jobs")["log"]]
    assert any("bị gián đoạn" in m and "chạy lại" in m for m in log)


def test_html_entities_like_python(ext):
    page = ('<meta property="og:title" content="Mom&rsquo;s Garden Flag &ndash; Custom&trade; &#9999999999; &#x1F436; &nbsp;x">'
            '<meta property="og:description" content="A&amp;B &eacute;t&eacute;">')
    py = shopify.from_html(page, "https://x/i")
    js = ext.js("h => SP.shopify.fromHtml(h, 'https://x/i')", page)
    assert js == py and js["title"].startswith("Mom’s Garden Flag – Custom™")
    rss = "<item><title>Caf&eacute; &amp; Mom&#8217;s</title></item>"
    assert kwtrends.parse_google_rss(rss) == ext.js("t => SP.kwtrends.parseGoogleRss(t)", rss)
    pin = json.dumps({"category": "Home decor", "trends": [{"category": "", "term": "Mugs", "pct_growth_wow": 0.5}]})
    assert kwtrends.parse_pinterest_text(pin) == ext.js("t => SP.kwtrends.parsePinterestText(t)", pin)
    assert html.unescape("&#0;") == ext.js("() => SP.shopify.fromHtml('<title>&#0;</title>', 'x').title")


def test_old_watch_country_and_follow_link(ext):
    ext.js("""async () => {
      for (const [p, k, c] of [["tiktok", "dog", "US"], ["tiktok", "dog", ""], ["fb_reels", "mug", "GB"], ["tiktok_ads", "", "US"]])
        await SP.db.put("social_watch", {platform: p, keyword: k, country: c, added_ts: 1, last_scan_ts: null});
      await SP.db.fixSocialWatchCountry();
    }""")
    assert sorted((w["platform"], w["keyword"], w["country"]) for w in ext.get("/api/viral/keywords")) == [
        ("fb_reels", "mug", ""), ("tiktok", "dog", ""), ("tiktok_ads", "", "US")]
    ext.post("/api/follows", {"kind": "shop", "key": " https://www.Bloomyard.com/products/x?y=1 "})
    assert ext.call("POST", "/api/follows", {"kind": "shop", "key": "https://"}, ok=False)["status"] == 400
    assert [(f["key"], f["name"]) for f in ext.get("/api/follows")] == [("bloomyard.com", "bloomyard.com")]
