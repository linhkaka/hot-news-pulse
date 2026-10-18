# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Lưu trữ kết quả (file JSON, giữ lại khi khởi động lại container)
# ============================================================================

import asyncio
import json
import os
from pathlib import Path

from .models import OutlierRecord, WatchChannel


def _atomic_write(path: Path, items: list) -> None:
    payload = json.dumps([i.model_dump() for i in items], ensure_ascii=False, indent=1)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


class OutlierStore:
    def __init__(self, data_dir: str):
        self.path = Path(data_dir) / "outliers.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._records: dict[str, OutlierRecord] = {}
        if self.path.exists():
            for item in json.loads(self.path.read_text(encoding="utf-8")):
                record = OutlierRecord.model_validate(item)
                self._records[record.video_id] = record

    def __len__(self) -> int:
        return len(self._records)

    def get(self, video_id: str) -> OutlierRecord | None:
        return self._records.get(video_id)

    def list(self, market: str | None = None) -> list[OutlierRecord]:
        records = [r for r in self._records.values() if not market or r.market == market]
        return sorted(records, key=lambda r: r.analyzed_at, reverse=True)

    async def upsert(self, record: OutlierRecord) -> None:
        async with self._lock:
            self._records[record.video_id] = record
            _atomic_write(self.path, list(self._records.values()))

    async def delete(self, video_id: str) -> bool:
        async with self._lock:
            if self._records.pop(video_id, None) is None:
                return False
            _atomic_write(self.path, list(self._records.values()))
            return True


class WatchlistStore:
    def __init__(self, data_dir: str):
        self.path = Path(data_dir) / "watchlist.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._channels: dict[str, WatchChannel] = {}
        if self.path.exists():
            for item in json.loads(self.path.read_text(encoding="utf-8")):
                channel = WatchChannel.model_validate(item)
                self._channels[channel.channel_id] = channel

    def __len__(self) -> int:
        return len(self._channels)

    def get(self, channel_id: str) -> WatchChannel | None:
        return self._channels.get(channel_id)

    def list(self) -> list[WatchChannel]:
        return sorted(self._channels.values(), key=lambda c: c.added_at)

    async def upsert(self, channel: WatchChannel) -> None:
        async with self._lock:
            self._channels[channel.channel_id] = channel
            _atomic_write(self.path, list(self._channels.values()))

    async def delete(self, channel_id: str) -> bool:
        async with self._lock:
            if self._channels.pop(channel_id, None) is None:
                return False
            _atomic_write(self.path, list(self._channels.values()))
            return True
