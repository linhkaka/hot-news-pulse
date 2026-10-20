"""Chạy tiện ích thật trong Chromium (Playwright) và gọi API của nó như trang giao diện.

Cần: pip install playwright pytest pillow httpx (bản app ../snakemedia-pod dùng để so kết quả).
Chromium: biến SNAKEPOD_CHROMIUM, hoặc Chromium do Playwright cài (python -m playwright install chromium).
"""
import glob
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

EXT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXT.parent / "snakemedia-pod"))      # bản Python để so sánh kết quả

DAY = 86400
HOUR = 3600


def _chromium():
    if os.environ.get("SNAKEPOD_CHROMIUM"):
        return os.environ["SNAKEPOD_CHROMIUM"]
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    return found[-1] if found else None


class Ext:
    def __init__(self, ctx, sw, ext_id):
        self.ctx, self.sw, self.id = ctx, sw, ext_id
        self.errors = []
        self.page = self.open("dashboard.html")

    def url(self, path):
        return f"chrome-extension://{self.id}/{path}"

    def open(self, path):
        page = self.ctx.new_page()
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(self.url(path))
        return page

    def call(self, method, path, body=None, ok=True):
        r = self.page.evaluate("([m, p, b]) => chrome.runtime.sendMessage({type: 'api', method: m, path: p, body: b})",
                               [method, path, body])
        if ok:
            assert r["ok"], r
            return r["data"]
        return r

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body=None):
        return self.call("POST", path, body or {})

    def js(self, expr, arg=None):
        """Chạy trong phần nền (service worker); các module nằm trong self.SP."""
        return self.sw.evaluate(expr, arg)

    def dev(self, base, **config):
        cfg = {"SCROLL_PAUSE_MS": [300, 600], "LOAD_WAIT_MS": 800, "PREPARE_WAIT_MS": 800, "PAGE_GAP_S": [0, 0],
               "PASSIVE_DELAY_S": 1, "SAFETY_DEFAULT_LIMITS": {"facebook": {"min_gap_s": 0, "max_per_day": 100},
                                                               "tiktok": {"min_gap_s": 0, "max_per_day": 100}}}
        cfg.update(config)
        self.js("d => SP.setDev(d)", {"config": cfg, "matches": ["http://127.0.0.1/*", "http://localhost/*"],
                                      "urls": {"FB": base, "TIKTOK": base, "CREATIVE_CENTER": base + "/topads",
                                               "TREND_VIDEOS": base + "/trend-video", "TREND_TAGS": base + "/trend-hashtag",
                                               "TG_API": base + "/tg"}})

    def wait_idle(self, timeout=90):
        end = time.time() + timeout
        time.sleep(0.3)
        while time.time() < end:
            s = self.get("/api/jobs")
            if not s["current"] and not s["pending"]:
                return s
            time.sleep(0.3)
        raise AssertionError(f"việc chưa xong: {s}")


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture
def ext(pw, tmp_path):
    exe = _chromium()
    ctx = pw.chromium.launch_persistent_context(
        str(tmp_path / "profile"), headless=True,
        args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        **({"executable_path": exe} if exe else {"channel": "chromium"}))
    sw = None
    for _ in range(30):                      # phần nền có thể khởi động trước khi kịp nghe sự kiện -> hỏi lại nhiều lần
        if ctx.service_workers:
            sw = ctx.service_workers[0]
            break
        try:
            sw = ctx.wait_for_event("serviceworker", timeout=1000)
            break
        except Exception:
            pass
    assert sw, "phần nền của tiện ích không khởi động"
    for _ in range(100):                     # đợi module phần nền chạy xong
        if sw.evaluate("typeof self.SP !== 'undefined'"):
            break
        time.sleep(0.1)
    sw.evaluate("SP.ready")
    e = Ext(ctx, sw, sw.url.split("/")[2])
    yield e
    ctx.close()


# ---------------- trang Facebook / TikTok / Telegram GIẢ ----------------

def jpeg(pattern):
    im = Image.new("L", (90, 80), 0)
    d = ImageDraw.Draw(im)
    for i, on in enumerate(pattern):
        if on:
            d.rectangle([i * 10, 0, i * 10 + 9, 79], fill=255)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=95)
    return buf.getvalue()


def fb_ad(ad_id, page, shop, video, age, active=True):
    now = int(time.time())
    return {"ad_archive_id": ad_id, "page_id": page, "page_name": f"Page {page}", "is_active": active,
            "start_date": now - age * DAY, "end_date": None if active else now - DAY, "collation_count": 1,
            "snapshot": {"body": {"text": f"Video {video} amazing gadget"},
                         "link_url": f"http://{shop}/products/{video.lower()}?utm=fb",
                         "videos": [{"video_sd_url": f"http://127.0.0.1:{{port}}/v/{video}.mp4",
                                     "video_preview_image_url": f"http://127.0.0.1:{{port}}/thumb/{video}.jpg"}]}}


def tt_item(item_id, views, created, cover):
    return {"id": item_id, "desc": "Personalized dog mom shirt #dogmom", "createTime": created,
            "author": {"uniqueId": "shop1"},
            "stats": {"playCount": views, "diggCount": 1000, "commentCount": 10, "shareCount": 100, "collectCount": 5},
            "video": {"cover": cover, "duration": 15}}


@pytest.fixture
def fake():
    """1 máy chủ giả đóng vai Thư viện QC Facebook, shop Shopify, TikTok, Creative Center và Telegram."""
    thumbs = {"A": jpeg([1, 0, 1, 0, 1, 0, 1, 0, 1]), "B": jpeg([1, 1, 1, 0, 0, 0, 1, 1, 1])}
    state = {"page": 0, "search_pages": 0, "topads_pages": 0, "typed": None, "tg": [], "empty": False}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="text/html", code=200, headers=None):
            body = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            port = self.server.server_address[1]
            path = self.path.split("?")[0]
            now = int(time.time())
            if path.startswith("/ads/library"):
                if "checkpoint" in self.path:
                    return self._send("", code=302, headers={"Location": "/checkpoint/block/?next=1"})
                first = [] if state["empty"] else [self.server.ads[0][:2]]
                ssr = json.dumps({"r": first}).replace("{port}", str(port))
                self._send(f"""<html><body style="height:20000px">
<script type="application/json" data-sjs>{ssr}</script>
<script>
let busy = false;
window.addEventListener('scroll', async () => {{
  if (busy) return; busy = true;
  await fetch('/api/graphql/', {{method: 'POST', body: 'q'}});
  busy = false;
}});
</script></body></html>""")
            elif path.startswith("/checkpoint"):
                self._send("<html><title>Security check</title><body>checkpoint</body></html>")
            elif path.startswith("/thumb/"):
                self._send(thumbs[path[7]], "image/jpeg")
            elif path.endswith(".json"):
                created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 12 * DAY))
                self._send(json.dumps({"product": {"title": "Gadget", "created_at": created,
                                                   "variants": [{"price": "19.99"}]}}), "application/json")
            elif "/products/" in path:
                self._send('<html><title>Gadget</title><script src="https://cdn.shopify.com/s.js"></script></html>')
            elif path == "/search/video":
                cover = f"http://127.0.0.1:{port}/cover.jpg"
                ssr = json.dumps({"__DEFAULT_SCOPE__": {"search": {"items": [tt_item("1", 2_000_000, now - 100 * HOUR, cover)]}}})
                self._send(f"""<html><body style="height:20000px">
<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{ssr}</script>
<script>let busy=false;window.addEventListener('scroll',async()=>{{if(busy)return;busy=true;
await fetch('/api/search/item/full/?cursor=1');busy=false;}});</script></body></html>""")
            elif path.startswith("/api/search/item/full"):
                state["search_pages"] += 1
                cover = f"http://127.0.0.1:{port}/cover.jpg"
                items = ([tt_item("2", 50_000, now - 5 * HOUR, cover), tt_item("3", 900, now - 200 * HOUR, cover)]
                         if state["search_pages"] == 1 else [])
                self._send(json.dumps({"item_list": items}), "application/json")
            elif path == "/topads":
                self._send("""<html><body style="height:3000px">
<input placeholder="Search by keyword or brand">
<button id="more">View More</button>
<script>
document.querySelector('input').addEventListener('keydown', e => {
  if (e.key === 'Enter') fetch('/creative_radar_api/v1/top_ads/v2/list?keyword=' + encodeURIComponent(e.target.value));
});
document.querySelector('#more').addEventListener('click', () => fetch('/creative_radar_api/v1/top_ads/v2/list?page=2'));
</script></body></html>""")
            elif path.startswith("/creative_radar_api"):
                state["topads_pages"] += 1
                if "keyword=" in self.path:
                    state["typed"] = self.path.split("keyword=")[1]
                page = state["topads_pages"]
                mats = [{"id": f"ad{page}", "ad_title": f"Custom mug {page}", "brand_name": "MugCo", "like": 1000 * page,
                         "video_info": {"cover": f"http://127.0.0.1:{port}/cover.jpg", "video_url": {"720p": "v"}}}] if page <= 2 else []
                self._send(json.dumps({"data": {"materials": mats}}), "application/json")
            elif path == "/cover.jpg":
                self._send(jpeg([1, 0, 1, 1, 0, 0, 1, 0, 1]), "image/jpeg")
            elif path.endswith("/getUpdates"):
                self._send(json.dumps({"ok": True, "result": [{"message": {"chat": {"id": 4242}}}]}), "application/json")
            else:
                self.send_error(404)

        def do_POST(self):
            data = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path.startswith("/tg/"):
                state["tg"].append(json.loads(data))
                return self._send(json.dumps({"ok": True}), "application/json")
            state["page"] += 1
            batch = self.server.ads[state["page"]] if state["page"] < len(self.server.ads) and not state["empty"] else []
            body = "for (;;);" + json.dumps({"data": {"edges": [{"node": {"collated_results": batch}}]}})
            self._send(body.replace("{port}", str(self.server.server_address[1])), "application/json")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.state = state
    srv.port = srv.server_address[1]
    srv.base = f"http://127.0.0.1:{srv.port}"
    shop1, shop2 = f"127.0.0.1:{srv.port}", f"localhost:{srv.port}"
    srv.ads = [
        [fb_ad("1", "p1", shop1, "A", 10), fb_ad("2", "p2", shop2, "A", 9)],
        [fb_ad("3", "p1", shop1, "A", 12, active=False), fb_ad("4", "p3", shop1, "B", 3)],
        [fb_ad("5", "p4", shop2, "B", 2)],
    ]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
