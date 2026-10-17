# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Gemini Key Pool - xoay vòng nhiều API key, tự né key hết quota
# ============================================================================

import json
import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger("richtube.gemini")

API = "https://generativelanguage.googleapis.com/v1beta/models"
COOLDOWN_SECONDS = 60


class GeminiError(Exception):
    pass


def extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


class GeminiPool:
    def __init__(self, keys: list[str], model: str, http: httpx.AsyncClient):
        self.keys = keys
        self.model = model
        self.http = http
        self._next = 0
        self._cooldown_until: dict[str, float] = {}

    @property
    def size(self) -> int:
        return len(self.keys)

    def _ordered_keys(self) -> list[str]:
        now = time.monotonic()
        ready = [k for k in self.keys if self._cooldown_until.get(k, 0) <= now]
        if not ready:
            return []
        start = self._next % len(ready)
        self._next += 1
        return ready[start:] + ready[:start]

    async def _call(self, key: str, body: dict) -> httpx.Response:
        return await self.http.post(
            f"{API}/{self.model}:generateContent",
            headers={"x-goog-api-key": key},
            json=body,
            timeout=300,
        )

    async def generate_json(
        self, prompt: str, video_url: Optional[str] = None, video_seconds: int = 120, temperature: float = 0.7
    ) -> dict:
        if not self.keys:
            raise GeminiError("Chưa cấu hình GEMINI_API_KEYS")

        text_part = {"text": prompt}
        parts = [text_part]
        if video_url:
            parts = [
                {
                    "fileData": {"fileUri": video_url, "mimeType": "video/*"},
                    "videoMetadata": {"startOffset": "0s", "endOffset": f"{video_seconds}s"},
                },
                text_part,
            ]
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }

        keys = self._ordered_keys()
        if not keys:
            raise GeminiError("Tất cả Gemini key đang tạm khoá do hết quota, thử lại sau 1 phút")

        last_error = ""
        for key in keys:
            res = await self._call(key, body)
            if res.status_code == 400 and video_url:
                # Video riêng tư / quá dài / không hỗ trợ -> phân tích bằng transcript
                log.warning("Gemini không xem được video, chuyển sang chỉ dùng text: %s", res.text[:200])
                body["contents"][0]["parts"] = [text_part]
                video_url = None
                res = await self._call(key, body)
            if res.status_code in (429, 403, 500, 503):
                self._cooldown_until[key] = time.monotonic() + COOLDOWN_SECONDS
                last_error = f"{res.status_code}: {res.text[:200]}"
                log.warning("Gemini key ...%s lỗi %s, chuyển key khác", key[-4:], res.status_code)
                continue
            if res.status_code != 200:
                raise GeminiError(f"Gemini lỗi {res.status_code}: {res.text[:300]}")
            data = res.json()
            try:
                text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                return extract_json(text)
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                raise GeminiError(f"Gemini trả về dữ liệu không hợp lệ: {exc}") from exc

        raise GeminiError(f"Tất cả Gemini key đều lỗi. Lỗi cuối: {last_error}")
