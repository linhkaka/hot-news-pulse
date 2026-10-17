from datetime import datetime, timedelta, timezone

import pytest

import config
import tracker
import youtube
from store import Store
from telegram_bot import CommandBot
from test_tracker import FakeTelegram

NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeYTClient:
    def __init__(self):
        self.channels = {"@mine": {"id": "UC" + "a" * 22, "title": "Kênh Của Tôi", "uploads": "UU1"}}
        self.ids = ["v1", "v2"]
        self.stats = {"v1": 12000, "v2": 300}
        self.error = None
        self.video_calls = []

    def resolve_channel(self, text):
        return self.channels.get(text)

    def recent_video_ids(self, uploads, since):
        if self.error:
            raise self.error
        return self.ids

    def videos(self, ids):
        self.video_calls.append(list(ids))
        return [{"id": v, "title": f"Video {v}", "published": NOW - timedelta(hours=3),
                 "views": self.stats[v]} for v in ids]


def make(tmp_path, client=None):
    cfg = {**config.DEFAULTS, "youtube_api_key": "key"}
    store = Store(tmp_path / "t.db")
    tg = FakeTelegram()
    t = tracker.Tracker(cfg, None, tg, store)
    t.youtube = youtube.YouTubeScanner(cfg, client or FakeYTClient(), store, tg,
                                       t.threshold, tracker.format_age)
    return t


def test_alerts_once_and_skips_notified_videos(tmp_path):
    t = make(tmp_path)
    yt = t.youtube
    assert "Đã thêm kênh Kênh Của Tôi" in yt.add_channel("@mine")

    assert yt.scan_once() == 1
    msg = t.telegram.sent[0]
    assert "https://www.youtube.com/watch?v=v1" in msg
    assert "12,000" in msg and "3 giờ" in msg and "Kênh Của Tôi" in msg

    yt.client.stats["v2"] = 5000
    assert yt.scan_once() == 1
    # v1 was already announced, so its stats are not fetched again.
    assert yt.client.video_calls[-1] == ["v2"]
    assert yt.scan_once() == 0


def test_quota_error_pauses(tmp_path):
    t = make(tmp_path)
    t.youtube.add_channel("@mine")
    t.youtube.client.error = youtube.QuotaError("quota")
    t.youtube.scan_once()
    assert not t.youtube.ready(forced=True)


def test_bad_key_alerts_once(tmp_path):
    t = make(tmp_path)
    t.youtube.add_channel("@mine")
    t.youtube.client.error = youtube.ApiKeyError("API key not valid")
    t.youtube.scan_once()
    t.youtube.scan_once()
    assert len(t.telegram.sent) == 1 and "API key" in t.telegram.sent[0]


def test_youtube_commands(tmp_path):
    t = make(tmp_path)
    bot = CommandBot(t.telegram, t)
    assert "Chưa theo dõi kênh" in bot.handle("/channels")
    assert "Đã thêm kênh" in bot.handle("/addyt @mine")
    assert "❌" in bot.handle("/addyt @nope")
    assert "Kênh Của Tôi" in bot.handle("/channels")
    t.youtube.scan_once()
    assert "▶️ 12,000 view" in bot.handle("/top")
    status = bot.handle("/status")
    assert "Kênh đang theo dõi: 1" in status and "Facebook" not in status
    assert "Facebook chưa bật" in bot.handle("/mypages")
    assert "Đã bỏ kênh" in bot.handle("/removeyt " + "UC" + "a" * 22)
    assert t.store.active_channels() == []


def test_seed_channels_respects_removal(tmp_path):
    t = make(tmp_path)
    t.youtube.seed_channels(["@mine"])
    assert len(t.store.active_channels()) == 1
    t.store.remove_channel("UC" + "a" * 22)
    t.youtube.seed_channels(["@mine"])
    assert t.store.active_channels() == []


def test_run_once_scans_youtube_without_facebook(tmp_path):
    t = make(tmp_path)
    t.youtube.add_channel("@mine")
    import threading
    t.run(threading.Event(), once=True)
    assert len(t.telegram.sent) == 1


@pytest.mark.parametrize("text,expected", [
    ("UCabcdefghijklmnopqrstuv", ("id", "UCabcdefghijklmnopqrstuv")),
    ("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv", ("id", "UCabcdefghijklmnopqrstuv")),
    ("https://www.youtube.com/@KenhCuaToi", ("handle", "@KenhCuaToi")),
    ("@kenh.cua-toi", ("handle", "@kenh.cua-toi")),
    ("KenhCuaToi", ("handle", "@KenhCuaToi")),
    ("not a channel!", (None, None)),
])
def test_parse_channel_input(text, expected):
    assert youtube.parse_channel_input(text) == expected


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, params=None, timeout=None):
        endpoint = url.rsplit("/", 1)[1]
        self.calls.append((endpoint, params))
        return FakeResponse(self.routes[endpoint])


def test_client_parses_api_responses():
    session = FakeSession({
        "channels": {"items": [{"id": "UC1", "snippet": {"title": "Mine"},
                                "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
        "playlistItems": {"items": [
            {"contentDetails": {"videoId": "new", "videoPublishedAt": iso(NOW)}},
            {"contentDetails": {"videoId": "old", "videoPublishedAt": iso(NOW - timedelta(days=30))}},
        ], "nextPageToken": "more"},
        "videos": {"items": [
            {"id": "new", "snippet": {"title": "T", "publishedAt": iso(NOW)},
             "statistics": {"viewCount": "5432"}},
            {"id": "live", "snippet": {"liveBroadcastContent": "upcoming"}, "statistics": {}},
        ]},
    })
    c = youtube.YouTubeClient("key", session=session)
    assert c.resolve_channel("@mine") == {"id": "UC1", "title": "Mine", "uploads": "UU1"}
    assert session.calls[-1][1]["forHandle"] == "@mine"
    # Stops at the old video without requesting the next page.
    assert c.recent_video_ids("UU1", NOW - timedelta(days=7)) == ["new"]
    assert sum(1 for e, _ in session.calls if e == "playlistItems") == 1
    vids = c.videos(["new", "live"])
    assert [(v["id"], v["views"]) for v in vids] == [("new", 5432)]


@pytest.mark.parametrize("error,exc", [
    ({"code": 403, "message": "quota", "errors": [{"reason": "quotaExceeded"}]}, youtube.QuotaError),
    ({"code": 400, "message": "API key not valid. Please pass a valid API key.",
      "errors": [{"reason": "badRequest"}]}, youtube.ApiKeyError),
    ({"code": 404, "message": "not found", "errors": [{"reason": "playlistNotFound"}]},
     youtube.YouTubeError),
])
def test_client_error_mapping(error, exc):
    c = youtube.YouTubeClient("key", session=FakeSession({"videos": {"error": error}}))
    with pytest.raises(exc):
        c.videos(["x"])


def test_config_youtube_only(tmp_path, monkeypatch):
    for var in ("FB_USER_ACCESS_TOKEN", "FB_PAGE_IDS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt")
    monkeypatch.setenv("YT_CHANNELS", "@a, UCabcdefghijklmnopqrstuv")
    cfg = config.load_config(tmp_path / "none.json")
    assert cfg["youtube_channels"] == ["@a", "UCabcdefghijklmnopqrstuv"]
    assert not config.facebook_enabled(cfg)
