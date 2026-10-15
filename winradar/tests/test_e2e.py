"""Chạy thật toàn bộ luồng quét (Chromium + cuộn + bắt GraphQL + tải ảnh + đọc trang bán + chấm nhãn)
trên một trang Thư viện QC GIẢ dựng trên máy. Bỏ qua nếu máy không có Chromium."""
import glob
import importlib
import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image, ImageDraw

DAY = 86400


def _chromium():
    if os.environ.get("WINRADAR_CHROMIUM"):
        return os.environ["WINRADAR_CHROMIUM"]
    found = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
    return found[0] if found else None


def _jpeg(pattern):
    im = Image.new("L", (90, 80), 0)
    d = ImageDraw.Draw(im)
    for i, on in enumerate(pattern):
        if on:
            d.rectangle([i * 10, 0, i * 10 + 9, 79], fill=255)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=95)
    return buf.getvalue()


def _ad(ad_id, page, shop, video, age, active=True):
    now = int(time.time())
    return {"ad_archive_id": ad_id, "page_id": page, "page_name": f"Page {page}", "is_active": active,
            "start_date": now - age * DAY, "end_date": None if active else now - DAY, "collation_count": 1,
            "snapshot": {"body": {"text": f"Video {video} amazing gadget"},
                         "link_url": f"http://{shop}/products/{video.lower()}?utm=fb",
                         "videos": [{"video_sd_url": f"http://127.0.0.1:{{port}}/v/{video}.mp4",
                                     "video_preview_image_url": f"http://127.0.0.1:{{port}}/thumb/{video}.jpg"}]}}


@pytest.fixture
def fake_facebook():
    thumbs = {"A": _jpeg([1, 0, 1, 0, 1, 0, 1, 0, 1]), "B": _jpeg([1, 1, 1, 0, 0, 0, 1, 1, 1])}
    state = {"page": 0}

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
            path = self.path.split("?")[0]
            if path.startswith("/ads/library"):
                first = json.dumps({"r": [self.server.ads[0][:2]]}).replace("{port}", str(self.server.port))
                self._send(f"""<html><body style="height:20000px">
<script type="application/json" data-sjs>{first}</script>
<script>
let busy = false;
window.addEventListener('scroll', async () => {{
  if (busy) return; busy = true;
  await fetch('/api/graphql/', {{method: 'POST', body: 'q'}});
  busy = false;
}});
</script></body></html>""")
            elif path.startswith("/thumb/"):
                self._send(thumbs[path[7]], "image/jpeg")
            elif path.endswith(".json"):
                created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 12 * DAY))
                self._send(json.dumps({"product": {"title": "Gadget", "created_at": created,
                                                   "variants": [{"price": "19.99"}]}}), "application/json")
            elif "/products/" in path:
                self._send('<html><title>Gadget</title><script src="https://cdn.shopify.com/s.js"></script></html>')
            else:
                self.send_error(404)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            state["page"] += 1
            batch = self.server.ads[state["page"]] if state["page"] < len(self.server.ads) else []
            body = "for (;;);" + json.dumps({"data": {"edges": [{"node": {"collated_results": batch}}]}})
            self._send(body.replace("{port}", str(self.server.port)), "application/json")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.port = srv.server_address[1]
    shop1, shop2 = f"127.0.0.1:{srv.port}", f"localhost:{srv.port}"
    srv.ads = [
        [_ad("1", "p1", shop1, "A", 10), _ad("2", "p2", shop2, "A", 9)],
        [_ad("3", "p1", shop1, "A", 12, active=False), _ad("4", "p3", shop1, "B", 3)],
        [_ad("5", "p4", shop2, "B", 2)],
    ]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


@pytest.mark.skipif(not _chromium(), reason="không có Chromium")
def test_full_scan_against_fake_ad_library(tmp_path, monkeypatch, fake_facebook):
    monkeypatch.setenv("WINRADAR_DATA", str(tmp_path))
    monkeypatch.setenv("WINRADAR_HEADLESS", "1")
    monkeypatch.setenv("WINRADAR_CHROMIUM", _chromium())
    monkeypatch.delenv("WINRADAR_PROXY", raising=False)
    from winradar import config
    importlib.reload(config)
    monkeypatch.setattr(config, "PROXY_FILE", tmp_path / "proxy.txt")
    from winradar import analyze, db, jobs, landing, scraper
    for m in (db, analyze, landing, scraper, jobs):
        importlib.reload(m)
    monkeypatch.setattr(scraper, "BASE", f"http://127.0.0.1:{fake_facebook.port}/ads/library/")
    db.init()

    n = jobs.keyword_job("gadget", "US", 50)()

    assert n == 5
    videos = {v["title"].split()[1]: v for v in db.list_videos()}
    assert set(videos) == {"A", "B"}, videos.keys()
    a, b = videos["A"], videos["B"]
    assert round(a["video_age_days"]) == 12          # tính cả QC đã tắt
    assert a["ads_gone"] == 1 and a["shops_win"] == 2 and a["label"] == "win"
    assert a["price"] == "19.99" and a["platform"] == "shopify" and round(a["landing_age_days"]) == 12
    assert b["shops_active"] == 2 and b["label"] == "sap_win"
    assert a["thumb"] and (config.THUMB_DIR / a["thumb"]).exists()
