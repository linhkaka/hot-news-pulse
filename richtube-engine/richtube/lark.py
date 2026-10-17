# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Đồng bộ kết quả sang Lark Base (Bitable)
# ============================================================================

import time

import httpx

from .models import OutlierRecord


class LarkError(Exception):
    pass


def record_to_fields(record: OutlierRecord) -> dict:
    """Tên cột phải trùng 100% với bảng trong Lark Base (xem README)."""
    script_lines = [
        f"#{s.scene_id} [{s.estimated_time}] {s.beat_function}\n"
        f"🎙️ {s.voiceover_script}\n🎬 {s.visual_direction}\n🖼️ {s.visual_generation_prompt}\n🔊 {s.audio_sfx_cues}"
        for s in record.blueprint.production_script
    ]
    return {
        "Video ID": record.video_id,
        "Tiêu đề gốc": record.title,
        "Kênh": record.channel_name,
        "Thị trường": record.market,
        "Link": record.url,
        "TAE": record.tae_score,
        "VPH": record.current_vph,
        "Baseline VPH": record.baseline_vph,
        "Góc khai thác": record.deconstruction.exploitable_gaps.superior_angle_proposal,
        "Tiêu đề đề xuất": "\n".join(record.blueprint.packaging_blueprint.titles),
        "Prompt Thumbnail": "\n\n".join(
            t.ai_image_prompt for t in record.blueprint.packaging_blueprint.thumbnail_concepts
        ),
        "Kịch bản": "\n\n".join(script_lines),
    }


class LarkClient:
    def __init__(self, domain: str, app_id: str, app_secret: str, app_token: str, table_id: str, http: httpx.AsyncClient):
        self.domain = domain.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self.table_id = table_id
        self.http = http
        self._token = ""
        self._token_expires = 0.0

    @property
    def configured(self) -> bool:
        return all([self.app_id, self.app_secret, self.app_token, self.table_id])

    async def _tenant_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        res = await self.http.post(
            f"{self.domain}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=20,
        )
        data = res.json()
        if data.get("code") != 0:
            raise LarkError(f"Lark đăng nhập lỗi: {data.get('msg')}")
        self._token = data["tenant_access_token"]
        self._token_expires = time.monotonic() + int(data.get("expire", 7200)) - 300
        return self._token

    async def upsert_record(self, record: OutlierRecord) -> str:
        token = await self._tenant_token()
        base = f"{self.domain}/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
        headers = {"Authorization": f"Bearer {token}"}
        body = {"fields": record_to_fields(record)}
        if record.lark_record_id:
            res = await self.http.put(f"{base}/{record.lark_record_id}", headers=headers, json=body, timeout=20)
        else:
            res = await self.http.post(base, headers=headers, json=body, timeout=20)
        data = res.json()
        if data.get("code") != 0:
            raise LarkError(f"Lark Base lỗi {data.get('code')}: {data.get('msg')}")
        return data["data"]["record"]["record_id"]
