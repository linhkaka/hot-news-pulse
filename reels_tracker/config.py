"""Load settings from config.json, a .env file and environment variables."""

import json
import os
from pathlib import Path

DEFAULTS = {
    "graph_api_version": "v23.0",
    "user_access_token": "",
    "pages": [],
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "view_threshold": 5000,
    "poll_interval_seconds": 120,
    "max_reel_age_days": 7,
    # Tried in order; the first metric the API returns a value for is used.
    "view_metrics": ["fb_reels_total_plays", "blue_reels_play_count"],
    "db_path": "reels_tracker.db",
    # Warn on Telegram when the Facebook token expires within this many days.
    "token_warning_days": 7,
}

# Environment variables win over config.json, so secrets can stay out of it.
ENV_OVERRIDES = {
    "FB_USER_ACCESS_TOKEN": "user_access_token",
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "VIEW_THRESHOLD": "view_threshold",
    "POLL_INTERVAL_SECONDS": "poll_interval_seconds",
    "DB_PATH": "db_path",
}

INT_KEYS = ("view_threshold", "poll_interval_seconds", "max_reel_age_days", "token_warning_days")


def load_dotenv(path):
    """Minimal .env reader: KEY=VALUE lines, existing env vars are kept."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path):
    path = Path(path)
    load_dotenv(path.parent / ".env")

    user_cfg = {}
    if path.exists():
        user_cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg = {**DEFAULTS, **user_cfg}

    for env, key in ENV_OVERRIDES.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    # FB_PAGE_IDS=111,222 adds Pages without editing config.json.
    for page_id in filter(None, (p.strip() for p in os.environ.get("FB_PAGE_IDS", "").split(","))):
        if all(str(p["id"]) != page_id for p in cfg["pages"]):
            cfg["pages"] = [*cfg["pages"], {"id": page_id}]

    for key in INT_KEYS:
        cfg[key] = int(cfg[key])

    missing = [k for k in ("telegram_bot_token", "telegram_chat_id") if not cfg[k]]
    if missing:
        raise ValueError(f"Thiếu cấu hình bắt buộc: {', '.join(missing)}")
    if not cfg["user_access_token"] and not any(p.get("access_token") for p in cfg["pages"]):
        raise ValueError(
            "Cần 'user_access_token' (hoặc 'access_token' riêng cho từng Page) để đọc Reels"
        )
    return cfg
