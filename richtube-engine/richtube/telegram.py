# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Gửi thông báo Telegram
# ============================================================================

import html
import logging

import httpx

from .models import OutlierRecord

log = logging.getLogger("richtube.telegram")


def esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def format_record(record: OutlierRecord) -> str:
    titles = "\n".join(f"  {i+1}. {esc(t)}" for i, t in enumerate(record.blueprint.packaging_blueprint.titles))
    lark = f"✅ Lark: {esc(record.lark_record_id)}" if record.lark_synced else "⚪ Chưa đồng bộ Lark"
    return (
        f"🔥 <b>{esc(record.title)}</b>\n"
        f"[{esc(record.market)}] {esc(record.channel_name)}\n"
        f"⚡ TAE <b>{record.tae_score}x</b> · {record.current_vph:,} VPH (baseline {record.baseline_vph:,})\n\n"
        f"💡 <b>Góc vượt mặt:</b> {esc(record.deconstruction.exploitable_gaps.superior_angle_proposal)}\n\n"
        f"🏷️ <b>Tiêu đề đề xuất:</b>\n{titles}\n\n"
        f"🎬 {len(record.blueprint.production_script)} cảnh kịch bản · {lark}\n"
        f"{esc(record.url)}"
    )


class TelegramNotifier:
    def __init__(self, token: str, default_chat_id: str, http: httpx.AsyncClient):
        self.token = token
        self.default_chat_id = default_chat_id
        self.http = http

    @property
    def configured(self) -> bool:
        return bool(self.token)

    async def send(self, text: str, chat_id: str | None = None) -> None:
        target = chat_id or self.default_chat_id
        if not (self.token and target):
            return
        try:
            res = await self.http.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": target, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=20,
            )
            if res.status_code != 200:
                log.warning("Telegram lỗi %s: %s", res.status_code, res.text[:200])
        except httpx.HTTPError as exc:
            log.warning("Không gửi được Telegram: %s", exc)
