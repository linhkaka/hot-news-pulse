"""Chế độ an toàn: phát hiện checkpoint/captcha, tạm dừng nền tảng, nghỉ giữa các lượt, giới hạn mỗi ngày."""
import importlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from tests.test_e2e import _chromium


def test_detect_rules():
    from snakepod.safety import detect
    assert "checkpoint" in detect("facebook", "https://www.facebook.com/checkpoint/1501092823525282/")
    assert "2 bước" in detect("facebook", "https://www.facebook.com/two_step_verification/two_factor/")
    assert "đăng nhập" in detect("facebook", "https://www.facebook.com/login/?next=ads")
    assert "captcha" in detect("tiktok", "https://www.tiktok.com/search/video?q=x", has_captcha=True)
    assert "đăng nhập" in detect("tiktok", "https://www.tiktok.com/login?redirect_url=x")
    assert detect("facebook", "https://www.facebook.com/ads/library/?q=dog", "Ad Library") is None
    assert detect("tiktok", "https://www.tiktok.com/search/video?q=checkpoint+shirt", "TikTok") is None


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import db, jobs, safety, server
    for m in (db, safety, jobs, server):
        importlib.reload(m)
    db.init()
    return tmp_path


def test_gap_quota_and_block(env):
    from snakepod import db, safety
    clock = {"t": 1_000_000.0}
    slept = []

    def sleep(s):
        slept.append(s)
        clock["t"] += s
    now = lambda: clock["t"]
    logs = []
    safety.set_limits("tiktok", 60, 2)
    safety.before_scan("tiktok", logs.append, sleep=sleep, now=now)       # lượt 1: không phải chờ
    assert not slept
    safety.before_scan("tiktok", logs.append, sleep=sleep, now=now)       # lượt 2: phải nghỉ ~60 giây
    assert 59 <= sum(slept) <= 61 and "Nghỉ" in logs[-1]
    with pytest.raises(safety.Skipped, match="giới hạn"):                  # lượt 3: hết lượt trong ngày
        safety.before_scan("tiktok", logs.append, sleep=sleep, now=now)
    safety.block("facebook", "Facebook yêu cầu xác minh tài khoản (checkpoint)", "https://facebook.com/checkpoint/")
    with pytest.raises(safety.Skipped, match="tạm dừng"):
        safety.before_scan("facebook", logs.append, sleep=sleep, now=now)
    safety.resume("facebook")
    safety.before_scan("facebook", logs.append, sleep=sleep, now=now)
    with pytest.raises(ValueError):
        safety.set_limits("tiktok", 5, 2)


def test_safety_api(env):
    from snakepod import safety, server
    with TestClient(server.app) as c:
        st = {p["key"]: p for p in c.get("/api/safety").json()["platforms"]}
        assert st["facebook"]["blocked"] is None and st["tiktok"]["max_per_day"] == 20
        safety.block("tiktok", "TikTok hiện captcha (xác minh không phải robot)")
        assert c.get("/api/jobs").json()["blocked"]["tiktok"]["reason"].startswith("TikTok hiện captcha")
        assert c.post("/api/safety/resume/tiktok").status_code == 200
        assert c.get("/api/jobs").json()["blocked"] == {}
        assert c.post("/api/safety/limits", json={"platform": "facebook", "min_gap_s": 120, "max_per_day": 10}).status_code == 200
        st = {p["key"]: p for p in c.get("/api/safety").json()["platforms"]}
        assert st["facebook"]["min_gap_s"] == 120 and st["facebook"]["max_per_day"] == 10
        assert c.post("/api/safety/limits", json={"platform": "facebook", "min_gap_s": 1, "max_per_day": 10}).status_code == 400


@pytest.mark.skipif(_chromium() is None, reason="không có Chromium")
def test_scan_stops_and_pauses_on_checkpoint(env, monkeypatch):
    """Trang giả chuyển sang /checkpoint khi cuộn -> tool dừng ngay, tạm dừng Facebook, lượt sau bị bỏ qua."""
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path.startswith("/ads/library"):
                body = ('<html><body style="height:20000px"><script>window.addEventListener("scroll",()=>'
                        '{location.href="/checkpoint/123/"},{once:true});</script></body></html>')
            else:
                body = "<html><head><title>Security Check</title></head><body>Confirm your identity</body></html>"
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("SNAKEPOD_HEADLESS", "1")
        monkeypatch.setenv("SNAKEPOD_SCROLL_MS", "300,600")
        if _chromium():
            monkeypatch.setenv("SNAKEPOD_CHROMIUM", _chromium())
        monkeypatch.delenv("SNAKEPOD_PROXY", raising=False)
        from snakepod import config
        importlib.reload(config)
        monkeypatch.setattr(config, "PROXY_FILE", env / "proxy.txt")
        from snakepod import db, jobs, safety, scraper
        for m in (db, safety, scraper, jobs):
            importlib.reload(m)
        monkeypatch.setattr(scraper, "BASE", f"http://127.0.0.1:{srv.server_address[1]}/ads/library/")
        jobs.start_worker()
        jobs.submit("keyword", "Quét 'dog'", jobs.keyword_job("dog", "US", 50))
        for _ in range(120):
            if safety.blocked().get("facebook") and jobs.status()["current"] is None:
                break
            time.sleep(0.5)
        b = safety.blocked()["facebook"]
        assert "checkpoint" in b["reason"] and "/checkpoint/" in b["url"]
        assert db.list_scans()[0]["status"] == "checkpoint"
        jobs.submit("keyword", "Quét 'cat'", jobs.keyword_job("cat", "US", 50))
        for _ in range(60):
            if db.list_scans()[0]["target"] == "Quét 'cat'" and db.list_scans()[0]["status"] != "dang chay":
                break
            time.sleep(0.5)
        assert db.list_scans()[0]["status"] == "bo qua"          # đang tạm dừng -> không mở trình duyệt nữa
    finally:
        srv.shutdown()
