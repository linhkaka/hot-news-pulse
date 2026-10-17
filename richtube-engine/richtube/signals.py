# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Tín hiệu ngầm - Most Replayed Heatmap & Transcript (best-effort)
# ============================================================================

import asyncio
import logging
import re

import httpx

from .models import HeatmapPoint

log = logging.getLogger("richtube.signals")

# YouTube nhúng dữ liệu "Most Replayed" vào trang xem video, có 2 định dạng (cũ & mới)
_HEAT_OLD = re.compile(
    r'"heatMarkerRenderer":\{"timeRangeStartMillis":(\d+),"markerDurationMillis":(\d+),'
    r'"heatMarkerIntensityScoreNormalized":([\d.eE+-]+)'
)
_HEAT_NEW = re.compile(
    r'\{"startMillis":"(\d+)","durationMillis":"(\d+)","intensityScoreNormalized":([\d.eE+-]+)'
)

Marker = tuple[float, float, float]  # (bắt đầu giây, độ dài giây, cường độ 0..1)


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def parse_heatmap(html: str) -> list[Marker]:
    for pattern in (_HEAT_NEW, _HEAT_OLD):
        found = pattern.findall(html)
        if found:
            markers: dict[float, Marker] = {}
            for start, dur, score in found:
                st = int(start) / 1000
                markers[st] = (st, int(dur) / 1000, max(0.0, min(1.0, float(score))))
            return [markers[k] for k in sorted(markers)]
    return []


def _expand(markers: list[Marker], seed: int, keep, used: set[int]) -> tuple[int, int]:
    lo = hi = seed
    while lo - 1 >= 0 and lo - 1 not in used and keep(markers[lo - 1][2]):
        lo -= 1
    while hi + 1 < len(markers) and hi + 1 not in used and keep(markers[hi + 1][2]):
        hi += 1
    return lo, hi


def summarize_heatmap(markers: list[Marker], max_spikes: int = 3, max_drops: int = 1) -> tuple[list[HeatmapPoint], list[HeatmapPoint]]:
    """Tìm các đỉnh giữ chân (xem lại nhiều) và vùng trũng (bị tua qua)."""
    if len(markers) < 5:
        return [], []

    used: set[int] = set()
    spikes: list[tuple[int, int, float]] = []
    for idx in sorted(range(len(markers)), key=lambda i: markers[i][2], reverse=True):
        if len(spikes) >= max_spikes:
            break
        if idx in used or idx - 1 in used or idx + 1 in used:
            continue
        peak = markers[idx][2]
        lo, hi = _expand(markers, idx, lambda v, p=peak: v >= p * 0.85, used)
        used.update(range(lo - 1, hi + 2))
        spikes.append((lo, hi, peak))

    # Vùng trũng: bỏ 5% đầu & cuối (luôn thấp/cao bất thường)
    edge = max(1, len(markers) // 20)
    middle = range(edge, len(markers) - edge)
    drops: list[tuple[int, int, float]] = []
    taken: set[int] = set()
    for idx in sorted(middle, key=lambda i: markers[i][2]):
        if len(drops) >= max_drops:
            break
        if idx in taken:
            continue
        low = markers[idx][2]
        lo, hi = _expand(markers, idx, lambda v, lw=low: v <= lw + 0.05, taken)
        lo, hi = max(lo, edge), min(hi, len(markers) - edge - 1)
        taken.update(range(lo - 2, hi + 3))
        drops.append((lo, hi, low))

    def to_point(lo: int, hi: int, value: float) -> HeatmapPoint:
        start = markers[lo][0]
        end = markers[hi][0] + markers[hi][1]
        return HeatmapPoint(time_range=f"{fmt_ts(start)} - {fmt_ts(end)}", intensity=round(value, 2))

    spikes.sort(key=lambda s: s[0])
    return [to_point(*s) for s in spikes], [to_point(*d) for d in drops]


async def fetch_heatmap(http: httpx.AsyncClient, video_id: str) -> list[Marker]:
    try:
        res = await http.get(
            "https://www.youtube.com/watch",
            params={"v": video_id, "hl": "en"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Cookie": "CONSENT=YES+1; SOCS=CAI",
            },
            timeout=20,
            follow_redirects=True,
        )
        return parse_heatmap(res.text) if res.status_code == 200 else []
    except httpx.HTTPError as exc:
        log.warning("Không lấy được heatmap %s: %s", video_id, exc)
        return []


def _fetch_transcript_sync(video_id: str) -> list[tuple[float, str]]:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    transcripts = api.list(video_id)
    codes = [t.language_code for t in transcripts]
    preferred = [c for c in ("en", "en-US", "ja", "ko", "es", "de", "fr", "vi") if c in codes] or codes
    fetched = api.fetch(video_id, languages=preferred)
    return [(snippet.start, snippet.text) for snippet in fetched]


async def fetch_transcript(video_id: str, max_chars: int = 60_000) -> str:
    """Transcript có timecode, dạng "[mm:ss] câu thoại". Trả về "" nếu không lấy được."""
    try:
        lines = await asyncio.to_thread(_fetch_transcript_sync, video_id)
    except Exception as exc:  # thư viện ném nhiều loại lỗi khác nhau
        log.warning("Không lấy được transcript %s: %s", video_id, exc)
        return ""
    text = "\n".join(f"[{fmt_ts(start)}] {line}" for start, line in lines)
    return text[:max_chars]
