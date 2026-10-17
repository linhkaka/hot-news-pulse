from datetime import datetime, timezone

from richtube.youtube import baseline_vph, parse_channel_ref, parse_video_id, video_vph

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def test_parse_video_id():
    vid = "dQw4w9WgXcQ"
    for url in [
        vid,
        f"https://www.youtube.com/watch?v={vid}",
        f"https://www.youtube.com/watch?feature=share&v={vid}&t=10",
        f"https://youtu.be/{vid}?si=abc",
        f"https://www.youtube.com/shorts/{vid}",
        f"https://www.youtube.com/live/{vid}",
    ]:
        assert parse_video_id(url) == vid
    assert parse_video_id("https://www.youtube.com/@MagnatesMedia") is None
    assert parse_video_id("hello") is None


def test_parse_channel_ref():
    cid = "UC" + "a" * 22
    assert parse_channel_ref(f"https://www.youtube.com/channel/{cid}") == ("id", cid)
    assert parse_channel_ref("https://www.youtube.com/@MagnatesMedia/videos") == ("handle", "@MagnatesMedia")
    assert parse_channel_ref("@abc") == ("handle", "@abc")
    assert parse_channel_ref("https://www.youtube.com/user/foo") == ("username", "foo")
    assert parse_channel_ref("https://www.youtube.com/c/bar") == ("custom", "bar")
    assert parse_channel_ref("https://example.com") is None


def _video(vid, views, published):
    return {"id": vid, "snippet": {"publishedAt": published}, "statistics": {"viewCount": str(views)}}


def test_vph_and_baseline():
    v = _video("a", 1000, "2026-10-16T14:00:00Z")  # 10 giờ trước
    assert video_vph(v, NOW) == 100
    recent = [
        _video("a", 1000, "2026-10-16T14:00:00Z"),  # bị loại
        _video("b", 100, "2026-10-16T14:00:00Z"),   # 10 VPH
        _video("c", 200, "2026-10-16T14:00:00Z"),   # 20 VPH
        _video("d", 300, "2026-10-16T14:00:00Z"),   # 30 VPH
    ]
    assert baseline_vph(recent, exclude_id="a", now=NOW) == 20
    assert baseline_vph([], now=NOW) == 0
