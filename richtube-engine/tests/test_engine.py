import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from richtube import engine as engine_module
from richtube.config import Settings
from richtube.engine import Engine
from richtube.gemini import GeminiError, GeminiPool
from tests.conftest import sample_analysis

YT = "https://www.googleapis.com/youtube/v3"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
LARK = "https://open.larksuite.com/open-apis"
VID = "dQw4w9WgXcQ"
CHANNEL = "UC" + "x" * 22


def iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def video(vid, views, hours_ago, channel=CHANNEL, title="Video"):
    return {
        "id": vid,
        "snippet": {
            "title": title, "channelId": channel, "channelTitle": "MagnatesMedia", "description": "desc",
            "publishedAt": iso(hours_ago), "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{vid}/hq.jpg"}},
        },
        "statistics": {"viewCount": str(views)},
        "contentDetails": {"duration": "PT10M"},
    }


VIDEOS = {
    VID: video(VID, 50_000, 10, title="How One Secret Company Monopolized Chips"),  # 5000 VPH
    "aaaaaaaaaaa": video("aaaaaaaaaaa", 10_000, 100),  # 100 VPH
    "bbbbbbbbbbb": video("bbbbbbbbbbb", 20_000, 100),  # 200 VPH
    "ccccccccccc": video("ccccccccccc", 30_000, 100),  # 300 VPH
}
HEATMAP_HTML = "".join(
    f'{{"startMillis":"{i*10000}","durationMillis":"10000","intensityScoreNormalized":{v}}},'
    for i, v in enumerate([1, 0.4, 0.4, 0.8, 0.4, 0.05, 0.4, 0.4, 0.6, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4])
)


def gemini_reply(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]})


def videos_route(request: httpx.Request) -> httpx.Response:
    ids = request.url.params["id"].split(",")
    return httpx.Response(200, json={"items": [VIDEOS[i] for i in ids if i in VIDEOS]})


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        youtube_api_key="yt-key",
        gemini_api_keys="key-one,key-two",
        gemini_model="gemini-test",
        telegram_bot_token="tg-token",
        telegram_chat_id="111",
        lark_app_id="app", lark_app_secret="secret", lark_base_app_token="base", lark_table_id="tbl",
        data_dir=str(tmp_path),
    )


@pytest.fixture
def mocked(monkeypatch):
    async def fake_transcript(video_id):
        return "[00:00] If this factory disappeared..."

    monkeypatch.setattr(engine_module, "fetch_transcript", fake_transcript)
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{YT}/videos").mock(side_effect=videos_route)
        router.get(f"{YT}/channels").mock(return_value=httpx.Response(200, json={"items": [{
            "id": CHANNEL, "snippet": {"title": "MagnatesMedia", "country": "US"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UU" + "x" * 22}},
        }]}))
        router.get(f"{YT}/playlistItems").mock(return_value=httpx.Response(200, json={"items": [
            {"contentDetails": {"videoId": v}} for v in VIDEOS
        ]}))
        router.get(f"{YT}/commentThreads").mock(return_value=httpx.Response(200, json={"items": [
            {"snippet": {"topLevelComment": {"snippet": {"likeCount": 900, "textDisplay": "You forgot Zeiss!"}}}}
        ]}))
        router.get("https://www.youtube.com/watch").mock(return_value=httpx.Response(200, text=HEATMAP_HTML))
        router.post(f"{LARK}/auth/v3/tenant_access_token/internal").mock(
            return_value=httpx.Response(200, json={"code": 0, "tenant_access_token": "t-123", "expire": 7200})
        )
        router.post(f"{LARK}/bitable/v1/apps/base/tables/tbl/records").mock(
            return_value=httpx.Response(200, json={"code": 0, "data": {"record": {"record_id": "rec_001"}}})
        )
        router.post("https://api.telegram.org/bottg-token/sendMessage").mock(return_value=httpx.Response(200, json={"ok": True}))
        yield router


async def test_spy_full_pipeline(settings, mocked):
    gemini = mocked.post(GEMINI).mock(return_value=gemini_reply(sample_analysis(spikes=3, drops=1)))
    async with httpx.AsyncClient() as http:
        engine = Engine(settings, http)
        record = await engine.spy(f"https://youtu.be/{VID}", chat_id="222")

    assert record.video_id == VID
    assert record.market == "US"
    assert record.current_vph == 5000
    assert record.baseline_vph == 200
    assert record.tae_score == 25.0
    assert record.lark_synced and record.lark_record_id == "rec_001"
    assert [p.note for p in record.heatmap_peaks.retention_spikes] == ["spike note 0", "spike note 1", "spike note 2"]
    assert record.heatmap_peaks.retention_drops[0].note == "drop note 0"
    assert record.blueprint.packaging_blueprint.titles == ["T1", "T2", "T3"]
    assert record.duration_seconds == 600
    assert len(record.heatmap_curve) == 20 and record.heatmap_curve[0] == 1.0

    sent = json.loads(gemini.calls.last.request.content)
    parts = sent["contents"][0]["parts"]
    assert parts[0]["fileData"]["fileUri"] == f"https://www.youtube.com/watch?v={VID}"
    assert "You forgot Zeiss!" in parts[1]["text"]
    assert "If this factory disappeared" in parts[1]["text"]

    telegram_calls = [c for c in mocked.calls if "api.telegram.org" in str(c.request.url)]
    assert json.loads(telegram_calls[-1].request.content)["chat_id"] == "222"

    # Lưu vào file và đọc lại được sau khi khởi động lại
    async with httpx.AsyncClient() as http:
        reloaded = Engine(settings, http)
    assert reloaded.store.get(VID).tae_score == 25.0


async def test_lark_failure_keeps_result(settings, mocked):
    mocked.post(GEMINI).mock(return_value=gemini_reply(sample_analysis()))
    mocked.post(f"{LARK}/bitable/v1/apps/base/tables/tbl/records").mock(
        return_value=httpx.Response(200, json={"code": 1254045, "msg": "FieldNameNotFound"})
    )
    async with httpx.AsyncClient() as http:
        record = await Engine(settings, http).spy(VID)
    assert record.lark_synced is False
    texts = [json.loads(c.request.content)["text"] for c in mocked.calls if "api.telegram.org" in str(c.request.url)]
    assert any("FieldNameNotFound" in t for t in texts)


async def test_gemini_rotates_keys_and_falls_back_to_text(mocked):
    calls = []

    def handler(request):
        key = request.headers["x-goog-api-key"]
        has_video = "fileData" in request.content.decode()
        calls.append((key, has_video))
        if key == "key-one":
            return httpx.Response(429, text="quota")
        if has_video:
            return httpx.Response(400, text="video unsupported")
        return gemini_reply({"ok": True})

    mocked.post(GEMINI).mock(side_effect=handler)
    async with httpx.AsyncClient() as http:
        pool = GeminiPool(["key-one", "key-two"], "gemini-test", http)
        assert await pool.generate_json("hi", video_url="https://youtu.be/x") == {"ok": True}
        # key-one đang bị khoá -> lần sau chỉ dùng key-two
        assert await pool.generate_json("hi") == {"ok": True}
    assert calls == [("key-one", True), ("key-two", True), ("key-two", False), ("key-two", False)]


async def test_gemini_without_keys():
    async with httpx.AsyncClient() as http:
        with pytest.raises(GeminiError):
            await GeminiPool([], "m", http).generate_json("hi")


async def test_invalid_gemini_json_retries_then_fails(settings, mocked):
    mocked.post(GEMINI).mock(return_value=gemini_reply({"wrong": "shape"}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(GeminiError):
            await Engine(settings, http).spy(VID)
    assert mocked.routes[-1].call_count == 2


async def test_discover_builds_grid_and_analyzes_top(settings, mocked):
    rival = "UC" + "r" * 22
    VIDEOS["rrrrrrrrrrr"] = video("rrrrrrrrrrr", 90_000, 10, channel=rival, title="Rival hit")
    try:
        mocked.get(f"{YT}/search").mock(return_value=httpx.Response(200, json={"items": [
            {"id": {"videoId": "rrrrrrrrrrr"}}, {"id": {"videoId": VID}},
        ]}))
        responses = iter([gemini_reply({"queries": {"US": "chip monopoly"}}), gemini_reply(sample_analysis())])
        mocked.post(GEMINI).mock(side_effect=lambda request: next(responses))
        settings.discover_analyze_top = 1
        async with httpx.AsyncClient() as http:
            records = await Engine(settings, http).discover("https://www.youtube.com/@MagnatesMedia", ["US"])
    finally:
        VIDEOS.pop("rrrrrrrrrrr")

    # Video của chính kênh hạt giống bị loại; chỉ còn video đối thủ
    assert [r.video_id for r in records] == ["rrrrrrrrrrr"]
    assert records[0].market == "US"
    grid_msg = [json.loads(c.request.content)["text"] for c in mocked.calls if "api.telegram.org" in str(c.request.url)][0]
    assert "Lưới 3x3" in grid_msg and "Rival hit" in grid_msg


async def test_resync_lark_after_failure(settings, mocked):
    mocked.post(GEMINI).mock(return_value=gemini_reply(sample_analysis()))
    records_route = mocked.post(f"{LARK}/bitable/v1/apps/base/tables/tbl/records")
    records_route.mock(return_value=httpx.Response(200, json={"code": 1254045, "msg": "FieldNameNotFound"}))
    async with httpx.AsyncClient() as http:
        engine = Engine(settings, http)
        assert (await engine.spy(VID, notify=False)).lark_synced is False
        records_route.mock(return_value=httpx.Response(200, json={"code": 0, "data": {"record": {"record_id": "rec_9"}}}))
        record = await engine.sync_lark(VID)
    assert record.lark_synced and record.lark_record_id == "rec_9"
    assert engine.store.get(VID).lark_record_id == "rec_9"


async def test_radar_scan_analyzes_new_outliers_once(settings, mocked):
    mocked.post(GEMINI).mock(return_value=gemini_reply(sample_analysis()))
    settings.radar_min_tae = 3.0
    async with httpx.AsyncClient() as http:
        engine = Engine(settings, http)
        watched = await engine.watch(f"https://www.youtube.com/channel/{CHANNEL}")
        assert watched.title == "MagnatesMedia" and watched.market == "US"

        first = await engine.radar_scan(chat_id="333")
        # Chỉ VID (10 giờ tuổi, TAE 25x) đạt; các video 100 giờ tuổi bị bỏ vì quá 72h
        assert [r.video_id for r in first] == [VID]
        assert engine.watchlist.get(CHANNEL).last_scanned_at is not None

        # Lần quét sau không phân tích lại video đã có
        assert await engine.radar_scan() == []

    texts = [json.loads(c.request.content)["text"] for c in mocked.calls if "api.telegram.org" in str(c.request.url)]
    assert any("Radar phát hiện 1 video" in t for t in texts)


async def test_radar_rejects_concurrent_scan(settings, mocked):
    async with httpx.AsyncClient() as http:
        engine = Engine(settings, http)
        async with engine.radar_lock:
            with pytest.raises(RuntimeError):
                await engine.radar_scan()


async def test_import_record_from_extension(settings, mocked):
    from richtube.models import OutlierRecord

    record = OutlierRecord.model_validate({
        "video_id": VID, "title": "From Chrome", "channel_name": "c", "market": "US",
        "url": f"https://www.youtube.com/watch?v={VID}", "thumbnail_url": "", "tae_score": 4.2,
        "current_vph": 100, "baseline_vph": 24, "published_hours_ago": 3, "lark_synced": True,
        "heatmap_curve": [0.5, 1.0], "heatmap_peaks": {}, **sample_analysis(),
    })
    async with httpx.AsyncClient() as http:
        engine = Engine(settings, http)
        saved = await engine.import_record(record, chat_id="444")
    # lark_synced do client gửi lên không được tin; Engine tự đồng bộ thật
    assert saved.lark_synced and saved.lark_record_id == "rec_001"
    assert engine.store.get(VID).title == "From Chrome"
    texts = [json.loads(c.request.content)["text"] for c in mocked.calls if "api.telegram.org" in str(c.request.url)]
    assert any("From Chrome" in t for t in texts)
