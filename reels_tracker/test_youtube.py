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


CH = "UC" + "a" * 22


def rss_video(vid, views, hours_ago=3, shorts=False):
    return {"id": vid, "title": f"Video {vid}", "published": NOW - timedelta(hours=hours_ago),
            "views": views,
            "link": f"https://www.youtube.com/{'shorts/' + vid if shorts else 'watch?v=' + vid}"}


class FakeRSS:
    def __init__(self):
        self.videos = [rss_video("v1", 12000, shorts=True), rss_video("v2", 300)]
        self.error = None

    def feed(self, channel_id):
        if self.error:
            raise self.error
        return {"title": "Kênh Của Tôi", "videos": list(self.videos)}


class FakeAPI:
    def __init__(self):
        self.stats = {}
        self.error = None
        self.video_calls = []
        self.playlist_ids = []
        self.units_today = 0

    def resolve_channel(self, text):
        if text == "@mine":
            return {"id": CH, "title": "Kênh Của Tôi", "uploads": "UU1"}
        return None

    def recent_video_ids(self, uploads, since):
        return self.playlist_ids

    def videos(self, ids):
        if self.error:
            raise self.error
        self.video_calls.append(list(ids))
        return [{"id": v, "title": f"Video {v}", "published": NOW - timedelta(hours=3),
                 "views": self.stats[v]} for v in ids if v in self.stats]


def make(tmp_path, api=None):
    cfg = {**config.DEFAULTS}
    store = Store(tmp_path / "t.db")
    tg = FakeTelegram()
    t = tracker.Tracker(cfg, None, tg, store)
    t.youtube = youtube.YouTubeScanner(cfg, store, tg, t.threshold, tracker.format_age,
                                       rss=FakeRSS(), api=api)
    return t


def test_rss_only_mode_alerts_once_with_exact_link(tmp_path):
    t = make(tmp_path)
    yt = t.youtube
    assert "Đã thêm kênh Kênh Của Tôi" in yt.add_channel(CH)

    assert yt.scan_once() == 1
    msg = t.telegram.sent[0]
    assert "https://www.youtube.com/shorts/v1" in msg
    assert "12,000" in msg and "3 giờ" in msg and "Kênh Của Tôi" in msg

    yt.rss.videos[1]["views"] = 5000
    assert yt.scan_once() == 1
    assert "watch?v=v2" in t.telegram.sent[1]
    assert yt.scan_once() == 0


def test_rss_mode_rejects_handles(tmp_path):
    t = make(tmp_path)
    msg = t.youtube.add_channel("@mine")
    assert "YOUTUBE_API_KEY" in msg and "UC" in msg
    assert t.store.active_channels() == []


def test_api_mode_batches_stats_and_skips_notified(tmp_path):
    api = FakeAPI()
    api.stats = {"v1": 12000, "v2": 300}
    t = make(tmp_path, api)
    yt = t.youtube
    yt.rss.videos = [rss_video("v1", None), rss_video("v2", None)]  # RSS views unused
    assert "Đã thêm kênh" in yt.add_channel("@mine")
    assert yt.scan_once() == 1
    assert api.video_calls == [["v1", "v2"]]
    api.stats["v2"] = 6000
    assert yt.scan_once() == 1
    # v1 was already announced, so its stats are not fetched again.
    assert api.video_calls[-1] == ["v2"]


def test_api_fills_in_when_rss_is_full(tmp_path):
    api = FakeAPI()
    t = make(tmp_path, api)
    yt = t.youtube
    yt.rss.videos = [rss_video(f"r{i}", None) for i in range(15)]
    api.playlist_ids = [f"r{i}" for i in range(15)] + ["extra"]
    api.stats = {"extra": 9000}
    yt.add_channel("@mine")
    assert yt.scan_once() == 1
    assert "watch?v=extra" in t.telegram.sent[0]


def test_old_rss_videos_ignored(tmp_path):
    t = make(tmp_path)
    t.youtube.rss.videos = [rss_video("old", 99999, hours_ago=24 * 30)]
    t.youtube.add_channel(CH)
    assert t.youtube.scan_once() == 0


def test_quota_error_pauses(tmp_path):
    api = FakeAPI()
    api.error = youtube.QuotaError("quota")
    t = make(tmp_path, api)
    t.youtube.add_channel("@mine")
    t.youtube.scan_once()
    assert not t.youtube.ready(forced=True)


def test_bad_key_alerts_once(tmp_path):
    api = FakeAPI()
    api.error = youtube.ApiKeyError("API key not valid")
    t = make(tmp_path, api)
    t.youtube.add_channel("@mine")
    t.youtube.scan_once()
    t.youtube.scan_once()
    assert len(t.telegram.sent) == 1 and "API key" in t.telegram.sent[0]


def test_youtube_commands(tmp_path):
    t = make(tmp_path)
    bot = CommandBot(t.telegram, t)
    assert "Chưa theo dõi kênh" in bot.handle("/channels")
    assert "Đã thêm kênh" in bot.handle(f"/addyt https://www.youtube.com/channel/{CH}")
    assert "❌" in bot.handle("/addyt @nope")
    assert "Kênh Của Tôi" in bot.handle("/channels")
    t.youtube.scan_once()
    assert "▶️ 12,000 view" in bot.handle("/top")
    status = bot.handle("/status")
    assert "Kênh đang theo dõi: 1" in status and "RSS" in status and "Facebook" not in status
    assert "Facebook chưa bật" in bot.handle("/mypages")
    assert "Facebook chưa bật" in bot.handle("/addall")
    assert "Đã bỏ kênh" in bot.handle("/removeyt " + CH)
    assert t.store.active_channels() == []


def test_seed_channels_respects_removal(tmp_path):
    t = make(tmp_path)
    t.youtube.seed_channels([CH])
    assert len(t.store.active_channels()) == 1
    t.store.remove_channel(CH)
    t.youtube.seed_channels([CH])
    assert t.store.active_channels() == []


def test_run_once_scans_youtube_without_facebook(tmp_path):
    t = make(tmp_path)
    t.youtube.add_channel(CH)
    import threading
    t.run(threading.Event(), once=True)
    assert len(t.telegram.sent) == 1


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Kênh Demo</title>
 <entry>
  <id>yt:video:abc123</id>
  <yt:videoId>abc123</yt:videoId>
  <yt:channelId>UCaaaaaaaaaaaaaaaaaaaaaa</yt:channelId>
  <title>Short hot</title>
  <link rel="alternate" href="https://www.youtube.com/shorts/abc123"/>
  <published>2026-10-18T10:00:00+00:00</published>
  <media:group>
   <media:title>Short hot</media:title>
   <media:community>
    <media:starRating count="10" average="5.00" min="1" max="5"/>
    <media:statistics views="5432"/>
   </media:community>
  </media:group>
 </entry>
 <entry>
  <yt:videoId>def456</yt:videoId>
  <title>Video thường</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=def456"/>
  <published>2026-10-17T10:00:00+00:00</published>
 </entry>
</feed>"""


def test_parse_feed():
    feed = youtube.parse_feed(SAMPLE_FEED)
    assert feed["title"] == "Kênh Demo"
    first, second = feed["videos"]
    assert first["id"] == "abc123" and first["views"] == 5432
    assert first["link"] == "https://www.youtube.com/shorts/abc123"
    assert first["published"].year == 2026
    assert second["views"] is None and second["title"] == "Video thường"
    with pytest.raises(youtube.YouTubeError):
        youtube.parse_feed("not xml")


class FakeHTTP:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


def test_rss_client_http_errors():
    class S:
        def __init__(self, resp):
            self.resp = resp

        def get(self, url, params=None, timeout=None):
            assert params == {"channel_id": CH}
            return self.resp

    assert youtube.YouTubeRSS(S(FakeHTTP(200, SAMPLE_FEED))).feed(CH)["title"] == "Kênh Demo"
    with pytest.raises(youtube.YouTubeError, match="không tìm thấy"):
        youtube.YouTubeRSS(S(FakeHTTP(404, ""))).feed(CH)


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


def test_api_counts_quota_units():
    session = FakeSession({"videos": {"items": []}})
    c = youtube.YouTubeClient("key", session=session)
    c.videos([f"v{i}" for i in range(120)])
    assert c.units_today == 3  # 50 + 50 + 20


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
