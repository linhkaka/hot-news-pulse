# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: YouTube Data API v3 client + công cụ tính VPH / TAE
# ============================================================================

import re
from datetime import datetime, timezone
from statistics import median
from typing import Optional

import httpx

API = "https://www.googleapis.com/youtube/v3"

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIDEO_PATTERNS = [
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})"),
]


class YouTubeError(Exception):
    pass


def parse_video_id(url_or_id: str) -> Optional[str]:
    s = url_or_id.strip()
    if _VIDEO_ID.match(s):
        return s
    for pattern in _VIDEO_PATTERNS:
        m = pattern.search(s)
        if m:
            return m.group(1)
    return None


def parse_channel_ref(url: str) -> Optional[tuple[str, str]]:
    """Trả về (kiểu, giá trị): ("id", "UC..."), ("handle", "@abc"), ("username", "abc") hoặc ("custom", "abc")."""
    s = url.strip()
    if re.match(r"^UC[A-Za-z0-9_-]{22}$", s):
        return ("id", s)
    if re.match(r"^@[\w.\-]+$", s):
        return ("handle", s)
    m = re.search(r"/channel/(UC[A-Za-z0-9_-]{22})", s)
    if m:
        return ("id", m.group(1))
    m = re.search(r"/(@[\w.\-%]+)", s)
    if m:
        return ("handle", m.group(1))
    m = re.search(r"/user/([\w.\-]+)", s)
    if m:
        return ("username", m.group(1))
    m = re.search(r"/c/([\w.\-%]+)", s)
    if m:
        return ("custom", m.group(1))
    return None


def hours_since(published_at: str, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    return max((now - published).total_seconds() / 3600, 1.0)


def video_vph(video: dict, now: Optional[datetime] = None) -> float:
    views = int(video.get("statistics", {}).get("viewCount", 0))
    return views / hours_since(video["snippet"]["publishedAt"], now)


def baseline_vph(videos: list[dict], exclude_id: Optional[str] = None, now: Optional[datetime] = None) -> float:
    """VPH trung vị của các video gần đây trên kênh (bỏ video đang xét)."""
    values = [video_vph(v, now) for v in videos if v.get("id") != exclude_id]
    return median(values) if values else 0.0


def parse_duration(iso: str) -> int:
    """Đổi thời lượng ISO 8601 của YouTube (vd: PT1H2M3S) sang giây."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def best_thumbnail(snippet: dict) -> str:
    thumbs = snippet.get("thumbnails", {})
    for key in ("maxres", "standard", "high", "medium", "default"):
        if key in thumbs:
            return thumbs[key]["url"]
    return ""


class YouTubeClient:
    def __init__(self, api_key: str, http: httpx.AsyncClient):
        self.api_key = api_key
        self.http = http

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, **params) -> dict:
        if not self.api_key:
            raise YouTubeError("Chưa cấu hình YOUTUBE_API_KEY")
        params = {k: v for k, v in params.items() if v is not None}
        res = await self.http.get(f"{API}/{path}", params={**params, "key": self.api_key}, timeout=20)
        if res.status_code != 200:
            try:
                reason = res.json()["error"]["message"]
            except Exception:
                reason = res.text[:200]
            raise YouTubeError(f"YouTube API {path} lỗi {res.status_code}: {reason}")
        return res.json()

    async def videos(self, ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(ids), 50):
            data = await self._get(
                "videos", part="snippet,statistics,contentDetails", id=",".join(ids[i : i + 50])
            )
            out.extend(data.get("items", []))
        return out

    async def channel(self, ref: tuple[str, str]) -> dict:
        kind, value = ref
        if kind == "id":
            data = await self._get("channels", part="snippet,contentDetails,statistics", id=value)
        elif kind == "handle":
            data = await self._get("channels", part="snippet,contentDetails,statistics", forHandle=value)
        elif kind == "username":
            data = await self._get("channels", part="snippet,contentDetails,statistics", forUsername=value)
        else:
            found = await self._get("search", part="snippet", q=value, type="channel", maxResults=1)
            items = found.get("items", [])
            if not items:
                raise YouTubeError(f"Không tìm thấy kênh '{value}'")
            return await self.channel(("id", items[0]["snippet"]["channelId"]))
        items = data.get("items", [])
        if not items:
            raise YouTubeError(f"Không tìm thấy kênh '{value}'")
        return items[0]

    async def recent_uploads(self, channel: dict, limit: int = 20) -> list[dict]:
        playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]
        data = await self._get("playlistItems", part="contentDetails", playlistId=playlist, maxResults=limit)
        ids = [item["contentDetails"]["videoId"] for item in data.get("items", [])]
        return await self.videos(ids) if ids else []

    async def top_comments(self, video_id: str, limit: int = 60) -> list[str]:
        try:
            data = await self._get(
                "commentThreads", part="snippet", videoId=video_id, order="relevance",
                maxResults=min(limit, 100), textFormat="plainText",
            )
        except YouTubeError:
            return []  # Bình luận bị tắt hoặc video giới hạn
        comments = []
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append(f"[{top.get('likeCount', 0)} likes] {top.get('textDisplay', '')}")
        return comments

    async def search_videos(
        self, query: str, region: str, language: str, published_after: str, limit: int = 15
    ) -> list[str]:
        data = await self._get(
            "search", part="snippet", q=query, type="video", order="viewCount",
            regionCode=region, relevanceLanguage=language, publishedAfter=published_after,
            maxResults=limit,
        )
        return [item["id"]["videoId"] for item in data.get("items", []) if item.get("id", {}).get("videoId")]
