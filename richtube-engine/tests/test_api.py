import asyncio
import importlib
import time

import pytest
from fastapi.testclient import TestClient

from richtube import config
from tests.conftest import sample_analysis  # noqa: F401


@pytest.fixture
def make_client(monkeypatch, tmp_path):
    def factory(**env):
        base = {"DATA_DIR": str(tmp_path), "YOUTUBE_API_KEY": "yt", "GEMINI_API_KEYS": "g1"}
        base.update(env)
        for key in ["RICHTUBE_API_KEY", "YOUTUBE_API_KEY", "GEMINI_API_KEYS"]:
            monkeypatch.delenv(key, raising=False)
        for key, value in base.items():
            monkeypatch.setenv(key, value)
        monkeypatch.chdir(tmp_path)  # tránh đọc file .env thật
        config.get_settings.cache_clear()
        import main
        return TestClient(importlib.reload(main).app)
    yield factory
    config.get_settings.cache_clear()


def test_health_and_cors(make_client):
    with make_client() as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "online"
        assert res.json()["gemini_pool_size"] == 1

        pre = client.options(
            "/api/v1/spy/video",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        assert pre.headers["access-control-allow-origin"] == "http://localhost:3000"
        bad = client.options(
            "/api/v1/spy/video",
            headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in bad.headers


def test_validation_and_not_configured(make_client):
    with make_client(YOUTUBE_API_KEY="") as client:
        assert client.post("/api/v1/spy/video", json={"video_url": "not a link"}).status_code == 422
        res = client.post("/api/v1/spy/video", json={"video_url": "https://youtu.be/dQw4w9WgXcQ"})
        assert res.status_code == 503
        assert "YOUTUBE_API_KEY" in res.json()["detail"]
        assert client.post("/api/v1/discover/channel", json={"seed_channel_url": "nope"}).status_code == 422


def test_api_key_required(make_client):
    with make_client(RICHTUBE_API_KEY="secret") as client:
        body = {"video_url": "https://youtu.be/dQw4w9WgXcQ"}
        assert client.post("/api/v1/spy/video", json=body).status_code == 401
        assert client.post("/api/v1/spy/video", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get("/api/v1/outliers").status_code == 200  # đọc dữ liệu không cần key


def test_spy_job_lifecycle(make_client):
    from richtube.engine import Engine
    from richtube.models import OutlierRecord

    async def fake_spy(self, video_url, notify=True, chat_id=None, market=None):
        await asyncio.sleep(0.05)
        record = OutlierRecord.model_validate({
            "video_id": "dQw4w9WgXcQ", "title": "t", "channel_name": "c", "market": "US",
            "url": "u", "thumbnail_url": "", "tae_score": 3.2, "current_vph": 10, "baseline_vph": 3,
            "published_hours_ago": 5, "heatmap_peaks": {}, **sample_analysis(),
        })
        await self.store.upsert(record)
        return record

    original = Engine.spy
    Engine.spy = fake_spy
    try:
        with make_client() as client:
            job = client.post("/api/v1/spy/video", json={"video_url": "https://youtu.be/dQw4w9WgXcQ"}).json()
            assert job["status"] in ("queued", "running")
            for _ in range(50):
                job = client.get(f"/api/v1/jobs/{job['job_id']}").json()
                if job["status"] == "done":
                    break
                time.sleep(0.02)
            assert job["status"] == "done"
            assert job["result_video_ids"] == ["dQw4w9WgXcQ"]
            outliers = client.get("/api/v1/outliers").json()
            assert outliers[0]["tae_score"] == 3.2
            assert client.get("/api/v1/outliers?market=JP").json() == []
            assert client.get("/api/v1/outliers/dQw4w9WgXcQ").status_code == 200
            assert client.get("/api/v1/jobs/nope").status_code == 404
    finally:
        Engine.spy = original


def _record(video_id="dQw4w9WgXcQ"):
    from richtube.models import OutlierRecord

    return OutlierRecord.model_validate({
        "video_id": video_id, "title": "Chip | Monopoly", "channel_name": "c", "market": "US",
        "url": f"https://www.youtube.com/watch?v={video_id}", "thumbnail_url": "", "tae_score": 3.2,
        "current_vph": 10, "baseline_vph": 3, "published_hours_ago": 5, "heatmap_peaks": {}, **sample_analysis(),
    })


def test_export_delete_and_record_actions(make_client):
    with make_client() as client:
        import asyncio as _asyncio

        engine = client.app.state.engine
        _asyncio.run(engine.store.upsert(_record()))

        md = client.get("/api/v1/outliers/dQw4w9WgXcQ/export.md")
        assert md.status_code == 200
        assert "attachment" in md.headers["content-disposition"]
        assert "| 1 | 00:00 - 00:07 | vo | vd | vgp | sfx |" in md.text
        csv_res = client.get("/api/v1/outliers/dQw4w9WgXcQ/export.csv")
        assert csv_res.text.startswith("\ufeffCảnh,Timecode")
        assert client.get("/api/v1/outliers/dQw4w9WgXcQ/export.pdf").status_code == 404

        # Lark chưa cấu hình -> 503 có hướng dẫn
        res = client.post("/api/v1/outliers/dQw4w9WgXcQ/sync-lark")
        assert res.status_code == 503 and "LARK" in res.json()["detail"]
        assert client.post("/api/v1/outliers/nope/reanalyze").status_code == 404

        assert client.delete("/api/v1/outliers/dQw4w9WgXcQ").status_code == 204
        assert client.get("/api/v1/outliers").json() == []
        assert client.delete("/api/v1/outliers/dQw4w9WgXcQ").status_code == 404


def test_watchlist_and_radar_endpoints(make_client):
    from richtube.engine import Engine
    from richtube.models import WatchChannel

    async def fake_watch(self, channel_url):
        item = WatchChannel(channel_id="UC" + "z" * 22, title="Rival", market="JP")
        await self.watchlist.upsert(item)
        return item

    original = Engine.watch
    Engine.watch = fake_watch
    try:
        with make_client(RICHTUBE_API_KEY="k") as client:
            h = {"X-API-Key": "k"}
            assert client.post("/api/v1/radar/run", headers=h).status_code == 400  # trống
            assert client.post("/api/v1/watchlist", json={"channel_url": "bad"}, headers=h).status_code == 422
            assert client.post("/api/v1/watchlist", json={"channel_url": "@rival"}).status_code == 401
            res = client.post("/api/v1/watchlist", json={"channel_url": "@rival"}, headers=h)
            assert res.status_code == 201 and res.json()["title"] == "Rival"
            assert [c["title"] for c in client.get("/api/v1/watchlist").json()] == ["Rival"]
            assert client.get("/health").json()["watchlist"] == 1
            assert client.delete(f"/api/v1/watchlist/{'UC' + 'z' * 22}", headers=h).status_code == 204
            assert client.get("/api/v1/watchlist").json() == []
    finally:
        Engine.watch = original
