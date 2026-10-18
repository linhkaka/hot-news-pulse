from richtube.signals import fmt_ts, heatmap_curve, parse_heatmap, summarize_heatmap


def _new_format(values, step_ms=10_000):
    return "".join(
        f'{{"startMillis":"{i*step_ms}","durationMillis":"{step_ms}","intensityScoreNormalized":{v}}},'
        for i, v in enumerate(values)
    )


def test_fmt_ts():
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(3725) == "1:02:05"


def test_parse_both_formats():
    new = parse_heatmap(_new_format([1, 0.5]))
    assert new == [(0.0, 10.0, 1.0), (10.0, 10.0, 0.5)]
    old = parse_heatmap(
        '"heatMarkerRenderer":{"timeRangeStartMillis":0,"markerDurationMillis":5000,"heatMarkerIntensityScoreNormalized":0.3}'
    )
    assert old == [(0.0, 5.0, 0.3)]
    assert parse_heatmap("<html>nothing</html>") == []


def test_summarize_finds_peaks_and_drop():
    values = [1.0, 0.9, 0.5, 0.4, 0.4, 0.8, 0.4, 0.4, 0.05, 0.06, 0.4, 0.4, 0.7, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.3]
    spikes, drops = summarize_heatmap(parse_heatmap(_new_format(values)))
    assert [s.time_range for s in spikes] == ["00:00 - 00:20", "00:50 - 01:00", "02:00 - 02:10"]
    assert spikes[0].intensity == 1.0
    assert len(drops) == 1 and drops[0].time_range == "01:20 - 01:40"
    assert drops[0].intensity == 0.05


def test_summarize_too_short():
    assert summarize_heatmap([(0, 1, 1)]) == ([], [])


def test_heatmap_curve_downsamples_keeping_peaks():
    markers = [(i, 1, 0.1) for i in range(250)]
    markers[123] = (123, 1, 0.9)
    curve = heatmap_curve(markers)
    assert len(curve) == 100
    assert max(curve) == 0.9
    assert heatmap_curve(markers[:10]) == [0.1] * 10
    assert heatmap_curve([]) == []
