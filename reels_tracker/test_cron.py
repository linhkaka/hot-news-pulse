"""--cron mode: every run is a fresh process sharing only the database."""
from datetime import datetime, timezone

import config
import tracker
import youtube
from store import Store
from telegram_bot import CommandBot
from test_tracker import FakeGraph, FakeTelegram
from test_youtube import CH, FakeRSS

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


class InboxTelegram(FakeTelegram):
    """FakeTelegram with an inbox like getUpdates."""
    chat_id = "42"

    def __init__(self, inbox):
        super().__init__()
        self.inbox = inbox
        self.offsets = []

    def get_updates(self, offset, timeout=50):
        self.offsets.append(offset)
        return [u for u in self.inbox if offset is None or u["update_id"] >= offset]


def msg(update_id, text, chat="42"):
    return {"update_id": update_id, "message": {"chat": {"id": int(chat)}, "text": text}}


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def new_run(tmp_path, inbox, clock, graph=None, rss=None):
    """Build everything from scratch, like a new GitHub Actions job."""
    cfg = {**config.DEFAULTS, "user_access_token": "u"}
    store = Store(tmp_path / "data" / "t.db")
    store.seed_pages([{"id": "p1", "name": "Page A", "access_token": "tok"}])
    tg = InboxTelegram(inbox)
    t = tracker.Tracker(cfg, graph or FakeGraph(), tg, store, clock=clock)
    t.youtube = youtube.YouTubeScanner(
        cfg, store, tg, t.threshold, tracker.format_age, rss=rss or FakeRSS(), clock=clock,
        interval_fn=lambda: t.scan_interval("youtube_poll_interval_seconds"))
    return t, tg


def test_cron_scans_when_due_and_skips_otherwise(tmp_path):
    clock = Clock()
    reels = [{"id": "r1", "permalink_url": "/reel/r1", "created_time": NOW}]
    g = FakeGraph(reels, {"r1": 100})

    t, tg = new_run(tmp_path, [], clock, g)
    t.run_cron(CommandBot(tg, t))
    assert any("Báo cáo view" in m for m in tg.sent)

    clock.now += 60  # next run 1 minute later: nothing due
    t, tg = new_run(tmp_path, [], clock, g)
    t.run_cron(CommandBot(tg, t))
    assert tg.sent == []

    clock.now += 1800 - 60 - 120  # 2 minutes early still counts (GitHub delays)
    g.views["r1"] = 400
    t, tg = new_run(tmp_path, [], clock, g)
    t.run_cron(CommandBot(tg, t))
    assert "Page A — 400 view (+300)" in tg.sent[-1]


def test_cron_answers_commands_once_and_forces_scan(tmp_path):
    clock = Clock()
    inbox = [msg(1, f"/addyt {CH}"), msg(2, "/threshold 50"), msg(3, "/hack", chat="7")]
    t, tg = new_run(tmp_path, [], clock)
    t.run_cron(CommandBot(tg, t))  # first run: scans, no commands yet

    clock.now += 60
    t, tg = new_run(tmp_path, inbox, clock)
    t.run_cron(CommandBot(tg, t))
    assert "Đã thêm kênh Kênh Của Tôi" in tg.sent[0]
    assert "50" in tg.sent[1]
    # /addyt forced a scan right away even though 30 minutes have not passed.
    assert any("Kênh Của Tôi —" in m for m in tg.sent if "Báo cáo" in m)
    assert all("hack" not in m for m in tg.sent)

    clock.now += 60
    t, tg = new_run(tmp_path, inbox, clock)
    t.run_cron(CommandBot(tg, t))
    assert tg.offsets == [4]  # commands are not answered twice
    assert tg.sent == []


def test_cron_status_shows_last_scan(tmp_path):
    clock = Clock()
    t, tg = new_run(tmp_path, [], clock)
    t.run_cron(CommandBot(tg, t))
    clock.now += 60
    t, tg = new_run(tmp_path, [msg(1, "/status")], clock)
    t.run_cron(CommandBot(tg, t))
    assert "chưa quét" not in tg.sent[0]


def test_cron_token_alert_not_repeated_every_run(tmp_path):
    clock = Clock()
    g = FakeGraph()
    g.error = tracker.TokenError(190, "expired")
    for _ in range(3):
        clock.now += 1800
        t, tg = new_run(tmp_path, [], clock, g)
        t.run_cron(CommandBot(tg, t))
        alerts = [m for m in tg.sent if "Token Facebook" in m]
        if _ == 0:
            assert len(alerts) == 1
        else:
            assert alerts == []


def test_cron_interval_command_is_respected(tmp_path):
    clock = Clock()
    t, tg = new_run(tmp_path, [msg(1, "/interval 60")], clock)
    t.run_cron(CommandBot(tg, t))
    clock.now += 1800  # 30 minutes later: not due with a 60-minute interval
    t, tg = new_run(tmp_path, [msg(1, "/interval 60")], clock)
    t.run_cron(CommandBot(tg, t))
    assert not any("Báo cáo" in m for m in tg.sent)
    clock.now += 1800
    t, tg = new_run(tmp_path, [], clock)
    t.run_cron(CommandBot(tg, t))
    assert any("Báo cáo" in m for m in tg.sent)


def test_cron_without_sources_sends_hint_once_a_day_not_empty_reports(tmp_path):
    clock = Clock()
    cfg = {**config.DEFAULTS}
    store = Store(tmp_path / "t.db")
    for i in range(3):
        tg = InboxTelegram([])
        t = tracker.Tracker(cfg, None, tg, store, clock=clock)
        t.youtube = youtube.YouTubeScanner(cfg, store, tg, t.threshold, tracker.format_age,
                                           rss=FakeRSS(), clock=clock)
        t.run_cron(CommandBot(tg, t))
        if i == 0:
            assert len(tg.sent) == 1 and "/addyt" in tg.sent[0]
            assert "/addall" not in tg.sent[0]
        else:
            assert tg.sent == []
        clock.now += 1800
