# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Settings (đọc từ biến môi trường / file .env)
# ============================================================================

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    youtube_api_key: str = ""
    gemini_api_keys: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_watch_video: bool = True

    title_language: str = "English"
    script_language: str = "Tiếng Việt"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_allowed_chat_ids: str = ""

    lark_domain: str = "https://open.larksuite.com"
    lark_app_id: str = ""
    lark_app_secret: str = ""
    lark_base_app_token: str = ""
    lark_table_id: str = ""

    richtube_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    data_dir: str = "data"
    discover_analyze_top: int = 3

    # Radar tự động quét các kênh trong danh sách theo dõi
    radar_interval_hours: float = 6  # 0 = tắt quét tự động
    radar_min_tae: float = 3.0
    radar_max_age_hours: int = 72
    radar_max_analyze: int = 3

    @property
    def gemini_keys(self) -> list[str]:
        return _split(self.gemini_api_keys)

    @property
    def cors_origin_list(self) -> list[str]:
        return _split(self.cors_origins)

    @property
    def allowed_chat_ids(self) -> set[str]:
        ids = set(_split(self.telegram_allowed_chat_ids))
        if not ids and self.telegram_chat_id:
            ids.add(self.telegram_chat_id)
        return ids

    @property
    def lark_configured(self) -> bool:
        return all([self.lark_app_id, self.lark_app_secret, self.lark_base_app_token, self.lark_table_id])

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
