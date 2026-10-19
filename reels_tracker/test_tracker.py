from datetime import datetime, timedelta, timezone

import pytest

import config
import graph as graph_mod
import tracker
from store import Store
from telegram_bot import CommandBot


class FakeGraph:
    def __init__(self, reels=None, views=None, managed=None):
        self.reels = reels or []
        self.views = views or {}
        self.managed = managed or {}
        self.error = None

    def page_tokens_from_user_token(self, user_token):
        return self.managed

    def recent_reels(self, page_id, token, since):
        if self.error:
            raise self.error
        return self.reels

    def reel_views(self, reel_id, token, metrics):
        return self.views.get(reel_id)

    def token_expires_at(self, token):
        return 0


class FakeTelegram:
    chat_id = "42"

    def __init__(self):
        self.sent = []
        self.documents = []

    def send(self, text, chat_id=None):
        self.sent.append(text)

    def send_long(self, text):
        self.sent.append(text)

    def send_document(self, filename, content, caption=""):
        self.documents.append((filename, content, caption))


def make_tracker(tmp_path, graph=None, **cfg_overrides):
    cfg = {**config.DEFAULTS, "user_access_token": "user-tok", **cfg_overrides}
    store = Store(tmp_path / "t.db")
    store.seed_pages([{"id": "p1", "name": "Page A", "access_token": "tok"}])
    return tracker.Tracker(cfg, graph or FakeGraph(), FakeTelegram(), store)


def test_notifies_once_when_threshold_crossed(tmp_path):
    reels = [
        {"id": "r1", "permalink_url": "/reel/r1", "description": "hot"},
        {"id": "r2", "permalink_url": "https://www.facebook.com/reel/r2"},
    ]
    g = FakeGraph(reels, {"r1": 6000, "r2": 4999})
    t = make_tracker(tmp_path, g)

    assert t.scan_once() == 1
    assert "https://www.facebook.com/reel/r1" in t.telegram.sent[0]
    assert "6,000" in t.telegram.sent[0]

    # Second scan: r1 already sent, r2 now crosses the threshold.
    g.views["r2"] = 5000
    assert t.scan_once() == 1
    assert "reel/r2" in t.telegram.sent[1]
    assert t.scan_once() == 0


def test_missing_metric_is_skipped(tmp_path):
    t = make_tracker(tmp_path, FakeGraph([{"id": "r1"}], {}))
    assert t.scan_once() == 0
    assert t.telegram.sent == []


def test_rate_limit_pauses_scanning(tmp_path):
    g = FakeGraph()
    g.error = graph_mod.RateLimitError(4, "too many calls")
    t = make_tracker(tmp_path, g)
    t.scan_once()
    assert t.cooldown_until > t.clock()


def test_token_error_alerts_once(tmp_path):
    g = FakeGraph()
    g.error = graph_mod.TokenError(190, "expired")
    t = make_tracker(tmp_path, g)
    t.scan_once()
    t.scan_once()
    assert len(t.telegram.sent) == 1
    assert "Token" in t.telegram.sent[0]


def test_commands(tmp_path):
    g = FakeGraph([{"id": "r1", "permalink_url": "/reel/r1"}], {"r1": 900},
                  managed={"555": ("Page B", "tok-b")})
    t = make_tracker(tmp_path, g)
    bot = CommandBot(t.telegram, t)

    assert "/add" in bot.handle("/help")
    assert "5,000" in bot.handle("/threshold")
    assert "800" in bot.handle("/threshold 800")
    assert t.threshold() == 800

    assert "Page B" in bot.handle("/mypages")
    assert "Đã thêm Page B" in bot.handle("/add@MyBot 555")
    assert "❌" in bot.handle("/add 999")
    assert "Page B" in bot.handle("/pages")
    assert "Đã bỏ" in bot.handle("/remove 555")
    assert "Page B" not in bot.handle("/pages")

    t.scan_once()  # 900 >= 800 -> alert
    assert "900" in t.telegram.sent[-1]
    assert "reel/r1" in bot.handle("/top")
    assert "Page đang theo dõi: 1" in bot.handle("/status")
    assert bot.handle("hello") is None


def test_removed_config_page_stays_removed(tmp_path):
    store = Store(tmp_path / "t.db")
    store.seed_pages([{"id": "1", "name": "A"}])
    store.remove_page("1")
    store.seed_pages([{"id": "1", "name": "A"}])
    assert store.active_pages() == []


def test_message_includes_age():
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    reel = {"id": "r", "created_time": "2026-10-17T09:30:00+0000"}
    assert "2 giờ 30 phút" in tracker.format_message("P", reel, 5000, 5000, now)


def test_config_env_overrides(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text('{"view_threshold": 7000}')
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("FB_USER_ACCESS_TOKEN", "fb")
    monkeypatch.setenv("FB_PAGE_IDS", "11, 22")
    cfg = config.load_config(tmp_path / "config.json")
    assert cfg["view_threshold"] == 7000
    assert [p["id"] for p in cfg["pages"]] == ["11", "22"]


def test_config_requires_telegram(tmp_path, monkeypatch):
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "FB_USER_ACCESS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValueError):
        config.load_config(tmp_path / "missing.json")


class FakeResponse:
    def __init__(self, data, headers=None):
        self._data = data
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url, params=None, timeout=None):
        if "video_insights" in url:
            return FakeResponse(self.responses["video_insights"][params["metric"]])
        return FakeResponse(self.responses["video_reels"])


def test_recent_reels_stops_at_old_reels():
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%S+0000"
    session = FakeSession({
        "video_reels": {"data": [
            {"id": "new", "created_time": now.strftime(fmt)},
            {"id": "old", "created_time": (now - timedelta(days=30)).strftime(fmt)},
        ]}
    })
    g = graph_mod.GraphClient("v23.0", session=session)
    reels = g.recent_reels("p", "t", now - timedelta(days=7))
    assert [r["id"] for r in reels] == ["new"]


def test_reel_views_falls_back_to_second_metric():
    session = FakeSession({
        "video_insights": {
            "fb_reels_total_plays": {"error": {"code": 100, "message": "invalid metric"}},
            "blue_reels_play_count": {"data": [{"values": [{"value": 7200}]}]},
        }
    })
    g = graph_mod.GraphClient("v23.0", session=session)
    metrics = ["fb_reels_total_plays", "blue_reels_play_count"]
    assert g.reel_views("r", "t", metrics) == 7200
    # The working metric is tried first next time.
    session.responses["video_insights"]["fb_reels_total_plays"] = None
    assert g.reel_views("r", "t", metrics) == 7200


def test_rate_limit_error_is_raised():
    session = FakeSession({"video_reels": {"error": {"code": 4, "message": "limit"}}})
    g = graph_mod.GraphClient("v23.0", session=session)
    with pytest.raises(graph_mod.RateLimitError):
        g.recent_reels("p", "t", datetime.now(timezone.utc))


def test_usage_header_parsing():
    header = '{"call_count": 12, "total_time": 85, "total_cputime": 3}'
    assert graph_mod._max_usage_percent(header) == 85
    assert graph_mod._max_usage_percent(None) == 0


def test_addall_adds_every_managed_page(tmp_path):
    g = FakeGraph(managed={"1": ("Page X", "t1"), "2": ("Page Y", "t2")})
    t = make_tracker(tmp_path, g)
    bot = CommandBot(t.telegram, t)
    assert "Đã thêm 2 Page" in bot.handle("/addall")
    assert "đã được theo dõi" in bot.handle("/addall")
    assert len(t.store.active_pages()) == 3


def test_many_pages_scanned_in_parallel(tmp_path):
    reels = [{"id": "r1", "permalink_url": "/reel/r1"}]
    g = FakeGraph(reels, {"r1": 7000}, managed={str(i): (f"P{i}", "t") for i in range(20)})
    t = make_tracker(tmp_path, g)
    t.add_all_pages()
    t.scan_once()
    # 20 managed Pages + the one seeded from config, all scanned by the worker pool.
    assert "21 Page" in t.last_scan_result
    assert t.telegram.sent


def test_old_reels_use_slow_lane(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    new = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
    reels = [{"id": "old", "created_time": old}, {"id": "new", "created_time": new}]

    class CountingGraph(FakeGraph):
        calls = []

        def reel_views(self, reel_id, token, metrics):
            self.calls.append(reel_id)
            return 10

    g = CountingGraph(reels)
    t = make_tracker(tmp_path, g)
    t.scan_once()
    t.scan_once()
    assert g.calls.count("new") == 2
    assert g.calls.count("old") == 1  # re-checked only after slow_check_interval_seconds


def test_default_interval_is_30_minutes_and_can_change(tmp_path):
    t = make_tracker(tmp_path)
    bot = CommandBot(t.telegram, t)
    assert t.scan_interval() == 1800
    assert "Quét mỗi: 30 phút" in bot.handle("/status")
    assert "30 phút" in bot.handle("/interval")

    t.last_scan_at = 1000.0
    assert "mỗi 60 phút" in bot.handle("/interval 60")
    assert t.scan_interval() == 3600
    assert t.scan_interval("youtube_poll_interval_seconds") == 3600
    assert t.fb_next_due == 1000.0 + 3600
    assert t.wakeup.is_set() and not t.scan_requested.is_set()
    assert "Quét mỗi: 1 giờ" in bot.handle("/status")

    assert "Đổi:" in bot.handle("/interval 0")
    assert "Đổi:" in bot.handle("/interval abc")
    assert t.scan_interval() == 3600


def test_interval_survives_restart(tmp_path):
    t = make_tracker(tmp_path)
    t.set_scan_interval(3600)
    t2 = tracker.Tracker(t.cfg, t.graph, t.telegram, Store(tmp_path / "t.db"))
    assert t2.scan_interval() == 3600
