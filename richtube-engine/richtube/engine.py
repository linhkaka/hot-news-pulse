# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Engine - ghép các bước Spy Video & Discover Channel
# ============================================================================

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from .analyzer import analyze, build_prompt
from .config import Settings
from .gemini import GeminiPool
from .lark import LarkClient
from .models import MARKETS, HeatmapPeaks, OutlierRecord, WatchChannel
from .signals import fetch_heatmap, fetch_transcript, heatmap_curve, summarize_heatmap
from .store import OutlierStore, WatchlistStore
from .telegram import TelegramNotifier, esc, format_record
from .youtube import (
    YouTubeClient,
    YouTubeError,
    baseline_vph,
    best_thumbnail,
    hours_since,
    parse_channel_ref,
    parse_duration,
    parse_video_id,
    video_vph,
)

log = logging.getLogger("richtube.engine")

MARKET_LANGUAGE = {"US": "en", "JP": "ja", "KR": "ko", "ES": "es", "DE": "de", "FR": "fr"}


def market_of(channel: dict) -> str:
    country = channel["snippet"].get("country", "")
    return country if country in MARKETS else (country or "GLOBAL")


class Engine:
    def __init__(self, settings: Settings, http: httpx.AsyncClient):
        self.settings = settings
        self.http = http
        self.youtube = YouTubeClient(settings.youtube_api_key, http)
        self.gemini = GeminiPool(settings.gemini_keys, settings.gemini_model, http)
        self.lark = LarkClient(
            settings.lark_domain, settings.lark_app_id, settings.lark_app_secret,
            settings.lark_base_app_token, settings.lark_table_id, http,
        )
        self.telegram = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id, http)
        self.store = OutlierStore(settings.data_dir)
        self.watchlist = WatchlistStore(settings.data_dir)
        self.radar_lock = asyncio.Lock()

    # ------------------------------------------------------------------ SPY
    async def spy(
        self, video_url: str, notify: bool = True, chat_id: Optional[str] = None, market: Optional[str] = None
    ) -> OutlierRecord:
        video_id = parse_video_id(video_url)
        if not video_id:
            raise ValueError(f"Link video không hợp lệ: {video_url}")

        found = await self.youtube.videos([video_id])
        if not found:
            raise YouTubeError(f"Không tìm thấy video {video_id} (video riêng tư hoặc đã xoá?)")
        video = found[0]
        snippet = video["snippet"]

        channel = await self.youtube.channel(("id", snippet["channelId"]))
        recent = await self.youtube.recent_uploads(channel)
        current = video_vph(video)
        baseline = baseline_vph(recent, exclude_id=video_id)
        tae = round(current / baseline, 1) if baseline > 0 else 0.0
        market = market or market_of(channel)

        markers, transcript, comments = await asyncio.gather(
            fetch_heatmap(self.http, video_id),
            fetch_transcript(video_id),
            self.youtube.top_comments(video_id),
        )
        spikes, drops = summarize_heatmap(markers)

        url = f"https://www.youtube.com/watch?v={video_id}"
        watch = self.settings.gemini_watch_video
        prompt = build_prompt(
            title=snippet["title"],
            channel=snippet["channelTitle"],
            description=snippet.get("description", ""),
            market=market,
            stats=f"{int(video['statistics'].get('viewCount', 0)):,} views, VPH {current:,.0f}, "
            f"baseline kênh {baseline:,.0f} VPH, TAE {tae}x",
            spikes=spikes,
            drops=drops,
            transcript=transcript,
            comments=comments,
            title_language=self.settings.title_language,
            script_language=self.settings.script_language,
            watching_video=watch,
        )
        result = await analyze(self.gemini, prompt, url if watch else None)

        for point, note in zip(spikes, result.spike_notes):
            point.note = note
        for point, note in zip(drops, result.drop_notes):
            point.note = note

        previous = self.store.get(video_id)
        record = OutlierRecord(
            video_id=video_id,
            title=snippet["title"],
            channel_name=snippet["channelTitle"],
            market=market,
            url=url,
            thumbnail_url=best_thumbnail(snippet),
            tae_score=tae,
            current_vph=round(current),
            baseline_vph=round(baseline),
            published_hours_ago=round(hours_since(snippet["publishedAt"])),
            duration_seconds=parse_duration(video.get("contentDetails", {}).get("duration", "")),
            heatmap_curve=heatmap_curve(markers),
            lark_record_id=previous.lark_record_id if previous else None,
            heatmap_peaks=HeatmapPeaks(retention_spikes=spikes, retention_drops=drops),
            deconstruction=result.deconstruction,
            blueprint=result.blueprint,
        )
        return await self._finalize(record, notify, chat_id)

    async def import_record(
        self, record: OutlierRecord, notify: bool = True, chat_id: Optional[str] = None
    ) -> OutlierRecord:
        """Nhận kết quả đã phân tích sẵn (vd: từ Tiện ích Chrome) rồi lưu, đồng bộ Lark, báo Telegram."""
        previous = self.store.get(record.video_id)
        record.lark_record_id = record.lark_record_id or (previous.lark_record_id if previous else None)
        record.lark_synced = False
        return await self._finalize(record, notify, chat_id)

    async def _finalize(self, record: OutlierRecord, notify: bool, chat_id: Optional[str]) -> OutlierRecord:
        if self.lark.configured:
            try:
                await self._push_lark(record)
            except Exception as exc:  # Lark lỗi không được làm mất kết quả phân tích
                log.warning("Đồng bộ Lark thất bại: %s", exc)
                if notify:
                    await self.telegram.send(f"⚠️ Đồng bộ Lark Base thất bại: {esc(exc)}", chat_id)

        await self.store.upsert(record)
        if notify:
            await self.telegram.send(format_record(record), chat_id)
        return record

    async def _push_lark(self, record: OutlierRecord) -> None:
        record.lark_record_id = await self.lark.upsert_record(record)
        record.lark_synced = True

    async def sync_lark(self, video_id: str) -> OutlierRecord:
        """Đồng bộ lại 1 video đã phân tích sang Lark Base (vd: sau khi sửa cấu hình Lark)."""
        record = self.store.get(video_id)
        if not record:
            raise KeyError(video_id)
        await self._push_lark(record)
        await self.store.upsert(record)
        return record

    # -------------------------------------------------------------- RADAR
    async def watch(self, channel_url: str) -> WatchChannel:
        ref = parse_channel_ref(channel_url)
        if not ref:
            raise ValueError(f"Link kênh không hợp lệ: {channel_url}")
        channel = await self.youtube.channel(ref)
        snippet = channel["snippet"]
        existing = self.watchlist.get(channel["id"])
        item = WatchChannel(
            channel_id=channel["id"],
            title=snippet["title"],
            market=market_of(channel),
            thumbnail_url=best_thumbnail(snippet),
            **({"added_at": existing.added_at, "last_scanned_at": existing.last_scanned_at} if existing else {}),
        )
        await self.watchlist.upsert(item)
        return item

    async def radar_scan(self, notify: bool = True, chat_id: Optional[str] = None) -> list[OutlierRecord]:
        """Quét video mới của các kênh theo dõi, tự mổ xẻ những video đột biến (TAE cao)."""
        if self.radar_lock.locked():
            raise RuntimeError("Radar đang quét, hãy đợi lượt hiện tại xong")
        async with self.radar_lock:
            s = self.settings
            candidates: list[tuple[float, str, dict]] = []
            for item in self.watchlist.list():
                try:
                    channel = await self.youtube.channel(("id", item.channel_id))
                    uploads = await self.youtube.recent_uploads(channel, limit=15)
                except YouTubeError as exc:
                    log.warning("Radar không quét được kênh %s: %s", item.title, exc)
                    continue
                for v in uploads:
                    if self.store.get(v["id"]) or hours_since(v["snippet"]["publishedAt"]) > s.radar_max_age_hours:
                        continue
                    base = baseline_vph(uploads, exclude_id=v["id"])
                    tae = video_vph(v) / base if base > 0 else 0
                    if tae >= s.radar_min_tae:
                        candidates.append((tae, item.market, v))
                item.last_scanned_at = datetime.now(timezone.utc).isoformat()
                await self.watchlist.upsert(item)

            candidates.sort(key=lambda c: c[0], reverse=True)
            picked = candidates[: s.radar_max_analyze]
            if notify and picked:
                lines = [
                    f"• <b>{tae:.1f}x</b> [{m}] {esc(v['snippet']['channelTitle'])} — {esc(v['snippet']['title'])}"
                    for tae, m, v in picked
                ]
                await self.telegram.send(
                    f"📡 <b>Radar phát hiện {len(candidates)} video đột biến</b>\n\n" + "\n".join(lines)
                    + "\n\n🔬 Đang mổ xẻ...",
                    chat_id,
                )

            records = []
            for _, market, v in picked:
                try:
                    records.append(await self.spy(v["id"], notify=notify, chat_id=chat_id, market=market))
                except Exception as exc:
                    log.warning("Radar mổ xẻ %s lỗi: %s", v["id"], exc)
            return records

    # ------------------------------------------------------------- DISCOVER
    async def discover(
        self, seed_channel_url: str, markets: list[str], notify: bool = True, chat_id: Optional[str] = None
    ) -> list[OutlierRecord]:
        ref = parse_channel_ref(seed_channel_url)
        if not ref:
            raise ValueError(f"Link kênh không hợp lệ: {seed_channel_url}")
        markets = [m for m in markets if m in MARKET_LANGUAGE] or list(MARKET_LANGUAGE)

        seed = await self.youtube.channel(ref)
        seed_id = seed["id"]
        seed_titles = [v["snippet"]["title"] for v in await self.youtube.recent_uploads(seed, limit=12)]

        plan = await self.gemini.generate_json(
            "Đây là kênh YouTube hạt giống:\n"
            f"Tên kênh: {seed['snippet']['title']}\n"
            f"Mô tả: {seed['snippet'].get('description', '')[:800]}\n"
            "Các video gần đây:\n- " + "\n- ".join(seed_titles) + "\n\n"
            "Hãy viết 1 cụm từ khoá tìm kiếm YouTube (2-5 từ) bằng NGÔN NGỮ BẢN ĐỊA cho từng thị trường "
            f"{', '.join(markets)} để tìm các kênh cùng ngách ở thị trường đó.\n"
            'Chỉ trả JSON dạng: {"queries": {"US": "...", "JP": "..."}}',
            temperature=0.4,
        )
        queries: dict = plan.get("queries", {})

        published_after = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        candidates: list[tuple[float, str, dict]] = []  # (tae, market, video)
        for market in markets:
            query = queries.get(market)
            if not query:
                continue
            try:
                ids = await self.youtube.search_videos(query, market, MARKET_LANGUAGE[market], published_after)
                videos = [v for v in await self.youtube.videos(ids) if v["snippet"]["channelId"] != seed_id]
            except YouTubeError as exc:
                log.warning("Tìm kiếm thị trường %s lỗi: %s", market, exc)
                continue
            best_per_channel: dict[str, dict] = {}
            for v in videos:
                cid = v["snippet"]["channelId"]
                if cid not in best_per_channel or video_vph(v) > video_vph(best_per_channel[cid]):
                    best_per_channel[cid] = v
            for v in list(best_per_channel.values())[:5]:
                try:
                    channel = await self.youtube.channel(("id", v["snippet"]["channelId"]))
                    base = baseline_vph(await self.youtube.recent_uploads(channel, limit=15), exclude_id=v["id"])
                except YouTubeError:
                    continue
                if base > 0:
                    candidates.append((video_vph(v) / base, market, v))

        candidates.sort(key=lambda c: c[0], reverse=True)
        grid = candidates[:9]
        if notify:
            lines = [
                f"{i+1}. [{m}] <b>{tae:.1f}x</b> · {esc(v['snippet']['channelTitle'])} — {esc(v['snippet']['title'])}"
                for i, (tae, m, v) in enumerate(grid)
            ]
            await self.telegram.send(
                f"🌐 <b>Lưới 3x3 đối thủ của {esc(seed['snippet']['title'])}</b>\n\n"
                + ("\n".join(lines) or "Không tìm thấy video outlier nào.")
                + f"\n\n🔬 Đang mổ xẻ sâu top {min(self.settings.discover_analyze_top, len(grid))} video...",
                chat_id,
            )

        records = []
        for _, market, v in grid[: self.settings.discover_analyze_top]:
            try:
                records.append(await self.spy(v["id"], notify=notify, chat_id=chat_id, market=market))
            except Exception as exc:
                log.warning("Mổ xẻ %s lỗi: %s", v["id"], exc)
        return records
