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
    # Scan every 30 minutes; change live with /interval in Telegram.
    "poll_interval_seconds": 1800,
    "max_reel_age_days": 7,
    # Tried in order; the first metric the API returns a value for is used.
    "view_metrics": ["fb_reels_total_plays", "blue_reels_play_count"],
    "db_path": "reels_tracker.db",
    "youtube_api_key": "",
    # Channel IDs (UC...), @handles or channel URLs.
    "youtube_channels": [],
    # New videos come from the free RSS feed; with an API key, view counts cost
    # 1 quota unit per 50 videos per scan (free quota: 10,000 units/day).
    "youtube_poll_interval_seconds": 1800,
    # Pages/channels scanned in parallel.
    "workers": 5,
    # Reels older than this are re-checked only every slow_check_interval_seconds,
    # which keeps Graph API usage low when many Pages are tracked.
    "fresh_hours": 24,
    "slow_check_interval_seconds": 600,
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
    "YOUTUBE_API_KEY": "youtube_api_key",
    "YOUTUBE_POLL_INTERVAL_SECONDS": "youtube_poll_interval_seconds",
    "WORKERS": "workers",
}

INT_KEYS = (
    "view_threshold",
    "poll_interval_seconds",
    "max_reel_age_days",
    "token_warning_days",
    "youtube_poll_interval_seconds",
    "workers",
    "fresh_hours",
    "slow_check_interval_seconds",
)


def facebook_enabled(cfg):
    return bool(cfg["user_access_token"]) or any(p.get("access_token") for p in cfg["pages"])


def _split_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


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
    for page_id in _split_list(os.environ.get("FB_PAGE_IDS", "")):
        if all(str(p["id"]) != page_id for p in cfg["pages"]):
            cfg["pages"] = [*cfg["pages"], {"id": page_id}]
    # YT_CHANNELS=@kenh1,UCxxxx adds YouTube channels the same way.
    for channel in _split_list(os.environ.get("YT_CHANNELS", "")):
        if channel not in cfg["youtube_channels"]:
            cfg["youtube_channels"] = [*cfg["youtube_channels"], channel]

    for key in INT_KEYS:
        cfg[key] = int(cfg[key])

    missing = [k for k in ("telegram_bot_token", "telegram_chat_id") if not cfg[k]]
    if missing:
        raise ValueError(f"Thiếu cấu hình bắt buộc: {', '.join(missing)}")
    cfg["workers"] = max(1, cfg["workers"])
    return cfg
