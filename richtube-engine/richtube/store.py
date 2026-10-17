# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Lưu trữ kết quả (file JSON, giữ lại khi khởi động lại container)
# ============================================================================

import asyncio
import json
import os
from pathlib import Path

from .models import OutlierRecord


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
            payload = json.dumps([r.model_dump() for r in self._records.values()], ensure_ascii=False, indent=1)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self.path)
