from datetime import datetime, timedelta, timezone

import tracker


class FakeGraph:
    def __init__(self, reels, views):
        self.reels = reels
        self.views = views

    def recent_reels(self, page_id, token, since):
        return self.reels

    def reel_views(self, reel_id, token, metrics):
        return self.views.get(reel_id)


class FakeTelegram:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


def make_cfg(**overrides):
    return {**tracker.DEFAULT_CONFIG, **overrides}


def test_notifies_once_when_threshold_crossed(tmp_path):
    reels = [
        {"id": "r1", "permalink_url": "/reel/r1", "description": "hot"},
        {"id": "r2", "permalink_url": "https://www.facebook.com/reel/r2"},
    ]
    graph = FakeGraph(reels, {"r1": 6000, "r2": 4999})
    tg = FakeTelegram()
    store = tracker.Store(tmp_path / "t.db")
    pages = [("p1", "Page A", "tok")]
    cfg = make_cfg()

    assert tracker.scan_once(cfg, graph, tg, store, pages) == 1
    assert "https://www.facebook.com/reel/r1" in tg.sent[0]
    assert "6,000" in tg.sent[0]

    # Second scan: r1 already sent, r2 now crosses the threshold.
    graph.views["r2"] = 5000
    assert tracker.scan_once(cfg, graph, tg, store, pages) == 1
    assert "reel/r2" in tg.sent[1]
    assert tracker.scan_once(cfg, graph, tg, store, pages) == 0


def test_missing_metric_is_skipped(tmp_path):
    graph = FakeGraph([{"id": "r1"}], {})
    tg = FakeTelegram()
    store = tracker.Store(tmp_path / "t.db")
    assert tracker.scan_once(make_cfg(), graph, tg, store, [("p", "P", "t")]) == 0


class FakeResponse:
    def __init__(self, data):
        self._data = data

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
    graph = tracker.GraphClient("v23.0", session=session)
    reels = graph.recent_reels("p", "t", now - timedelta(days=7))
    assert [r["id"] for r in reels] == ["new"]


def test_reel_views_falls_back_to_second_metric():
    session = FakeSession({
        "video_insights": {
            "fb_reels_total_plays": {"error": {"code": 100, "message": "invalid metric"}},
            "blue_reels_play_count": {"data": [{"values": [{"value": 7200}]}]},
        }
    })
    graph = tracker.GraphClient("v23.0", session=session)
    views = graph.reel_views("r", "t", ["fb_reels_total_plays", "blue_reels_play_count"])
    assert views == 7200
