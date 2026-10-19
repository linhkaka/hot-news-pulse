import threading
from datetime import datetime, timedelta, timezone

from report import ScanReport, format_report, snapshots_csv
from telegram_bot import CommandBot, Telegram
from test_tracker import FakeGraph, make_tracker
from test_youtube import CH, make as make_yt, rss_video

NOW = datetime.now(timezone.utc)


def test_first_scan_has_no_growth_numbers():
    r = ScanReport("facebook", NOW)
    r.add_source("p1", "Page A", seen_before=False)
    r.add_item("p1", "r1", "Caption 1", "https://fb/r1", NOW, 1000, None)
    (s,) = r.summaries()
    assert s["total"] == 1000 and s["delta"] is None
    text = format_report([r])
    assert "Page A — 1,000 view · 1 video" in text
    assert "(+" not in text.split("Tổng cộng")[0]


def test_growth_and_new_videos_after_first_scan():
    r = ScanReport("youtube", NOW)
    r.add_source("c1", "Kênh 1", seen_before=True)
    r.add_source("c2", "Kênh 2", seen_before=True)
    r.add_item("c1", "a", "Video A", "https://yt/a", NOW, 1500, 1000)   # +500
    r.add_item("c1", "b", "Video B", "https://yt/b", NOW, 300, None)    # new: +300
    r.add_item("c2", "c", "Video C", "https://yt/c", NOW, 9000, 9000)   # +0
    c1, c2 = sorted(r.summaries(), key=lambda s: s["name"])
    assert (c1["total"], c1["delta"], c1["new_videos"]) == (1800, 800, 1)
    assert (c2["total"], c2["delta"]) == (9000, 0)
    text = format_report([r], top_n=1)
    assert "Kênh 1 — 1,800 view (+800) · 2 video, 1 mới" in text
    # Fastest-growing video listed first under its channel.
    assert "↑ 1,500 (+500) — Video A" in text and "Video B" not in text
    assert "Tổng cộng: 10,800 view (+800)" in text
    # Channels are sorted by total views.
    assert text.index("Kênh 2") < text.index("Kênh 1")


def test_errors_are_listed():
    r = ScanReport("facebook", NOW)
    r.add_source("p1", "Page A", seen_before=True)
    r.mark_error("p1", "permission denied")
    assert "Page A — ⚠️ lỗi: permission denied" in format_report([r])


def test_csv_export_has_bom_and_rows():
    r = ScanReport("youtube", NOW)
    r.add_source("c1", "Kênh Việt", seen_before=False)
    r.add_item("c1", "a", "Tiêu đề", "https://yt/a", NOW, 42, None)
    data = snapshots_csv(r.snapshot_rows()).decode("utf-8")
    assert data.startswith("﻿Thời gian quét,")
    assert "Kênh Việt" in data and ",42" in data


def test_facebook_rereads_views_every_scan_and_reports(tmp_path):
    reels = [{"id": "r1", "permalink_url": "/reel/r1", "description": "Clip hay",
              "created_time": NOW.strftime("%Y-%m-%dT%H:%M:%S+0000")}]
    g = FakeGraph(reels, {"r1": 6000})
    t = make_tracker(tmp_path, g)
    t.run(threading.Event(), once=True)
    assert "Reel vượt" in t.telegram.sent[0]
    assert "Page A — 6,000 view · 1 video" in t.telegram.sent[1]

    g.views["r1"] = 8500
    t.telegram.sent.clear()
    t.run(threading.Event(), once=True)
    # No second alert, but the report shows the new count and growth.
    assert len(t.telegram.sent) == 1
    assert "Page A — 8,500 view (+2,500)" in t.telegram.sent[0]
    assert "https://www.facebook.com/reel/r1" in t.telegram.sent[0]


def test_youtube_report_and_history(tmp_path):
    t = make_yt(tmp_path)
    t.youtube.add_channel(CH)
    t.run(threading.Event(), once=True)
    t.youtube.rss.videos = [rss_video("v1", 12500, shorts=True), rss_video("v2", 900)]
    t.run(threading.Event(), once=True)
    report = t.telegram.sent[-1]
    assert "Kênh Của Tôi — 13,400 view (+1,100)" in report
    rows = t.store.snapshots_since("2000-01-01")
    assert len(rows) == 4  # 2 videos x 2 scans


def test_report_export_and_toggle_commands(tmp_path):
    reels = [{"id": "r1", "permalink_url": "/reel/r1"}]
    t = make_tracker(tmp_path, FakeGraph(reels, {"r1": 100}))
    bot = CommandBot(t.telegram, t)
    assert "Chưa có báo cáo" in bot.handle("/report")
    assert "Chưa có dữ liệu" in bot.handle("/export")

    t.run(threading.Event(), once=True)
    t.telegram.sent.clear()
    assert bot.handle("/report") is None
    assert "Báo cáo view" in t.telegram.sent[-1]

    assert bot.handle("/export 3") is None
    name, content, caption = t.telegram.documents[-1]
    assert name.endswith(".csv") and "3 ngày" in caption and b"reel/r1" in content

    assert "Tắt" in bot.handle("/report off")
    t.telegram.sent.clear()
    t.run(threading.Event(), once=True)
    assert t.telegram.sent == []  # still scanned and saved, just not sent
    assert len(t.store.snapshots_since("2000-01-01")) == 2
    assert "Sẽ gửi" in bot.handle("/report on")


def test_old_history_is_pruned(tmp_path):
    t = make_tracker(tmp_path, FakeGraph([{"id": "r1"}], {"r1": 1}))
    old = (NOW - timedelta(days=60)).isoformat()
    t.store.add_snapshots([(old, "facebook", "p1", "A", "x", "", "", None, 1)])
    t.run(threading.Event(), once=True)
    rows = t.store.snapshots_since("2000-01-01")
    assert all(r[0] != old for r in rows) and rows


def test_send_long_splits_on_lines():
    tg = Telegram("token", "1")
    chunks = []
    tg.send = chunks.append
    tg.send_long("\n".join(f"line {i:04d} " + "x" * 90 for i in range(100)), limit=1000)
    assert len(chunks) > 1 and all(len(c) <= 1000 for c in chunks)
    assert "\n".join(chunks).count("line ") == 100
