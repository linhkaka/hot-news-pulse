"""Facebook Reels -> Telegram tracker (official Graph API only).

Polls the Reels of Facebook Pages you manage, reads their play count from
the Graph API insights endpoint, and sends the Reel link to a Telegram chat
the first time a Reel crosses the view threshold.

Usage:
    python tracker.py              # run forever, polling every N seconds
    python tracker.py --once       # run one scan and exit (good for cron)
    python tracker.py --test-telegram   # send a test message and exit
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

log = logging.getLogger("reels_tracker")

DEFAULT_CONFIG = {
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
}


class GraphAPIError(Exception):
    pass


def load_config(path):
    with open(path, encoding="utf-8") as f:
        user_cfg = json.load(f)
    cfg = {**DEFAULT_CONFIG, **user_cfg}
    missing = [k for k in ("telegram_bot_token", "telegram_chat_id") if not cfg[k]]
    if missing:
        raise ValueError(f"Missing required config: {', '.join(missing)}")
    if not cfg["pages"]:
        raise ValueError("Config 'pages' is empty: add at least one Page")
    return cfg


class GraphClient:
    def __init__(self, version, session=None):
        self.base = f"https://graph.facebook.com/{version}"
        self.session = session or requests.Session()

    def get(self, path, token, **params):
        params["access_token"] = token
        resp = self.session.get(f"{self.base}/{path}", params=params, timeout=30)
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise GraphAPIError(f"{err.get('code')}: {err.get('message')}")
        return data

    def page_tokens_from_user_token(self, user_token):
        """Map page_id -> page access token for every Page the user manages."""
        tokens = {}
        data = self.get("me/accounts", user_token, fields="id,name,access_token", limit=100)
        while True:
            for page in data.get("data", []):
                tokens[page["id"]] = page["access_token"]
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                return tokens
            data = self.session.get(next_url, timeout=30).json()

    def recent_reels(self, page_id, token, since):
        """Reels on a Page created after `since` (newest first)."""
        data = self.get(
            f"{page_id}/video_reels",
            token,
            fields="id,description,permalink_url,created_time",
            limit=50,
        )
        reels = []
        while True:
            for reel in data.get("data", []):
                created = parse_fb_time(reel.get("created_time"))
                if created and created < since:
                    return reels
                reels.append(reel)
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                return reels
            data = self.session.get(next_url, timeout=30).json()

    def reel_views(self, reel_id, token, metrics):
        """Return the view count of a Reel, or None if no metric is available."""
        for metric in metrics:
            try:
                data = self.get(f"{reel_id}/video_insights", token, metric=metric)
            except GraphAPIError as e:
                log.debug("Metric %s unavailable for %s: %s", metric, reel_id, e)
                continue
            for item in data.get("data", []):
                values = item.get("values") or []
                if values and isinstance(values[0].get("value"), (int, float)):
                    return int(values[0]["value"])
        return None


class Telegram:
    def __init__(self, bot_token, chat_id, session=None):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id
        self.session = session or requests.Session()

    def send(self, text):
        resp = self.session.post(
            self.url,
            json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": False},
            timeout=30,
        )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram error: {data.get('description')}")


class Store:
    """Remembers which Reels were already announced, so each is sent once."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS notified (
                reel_id TEXT PRIMARY KEY,
                page_id TEXT,
                views INTEGER,
                link TEXT,
                notified_at TEXT
            )"""
        )
        self.conn.commit()

    def was_notified(self, reel_id):
        cur = self.conn.execute("SELECT 1 FROM notified WHERE reel_id = ?", (reel_id,))
        return cur.fetchone() is not None

    def mark_notified(self, reel_id, page_id, views, link):
        self.conn.execute(
            "INSERT OR IGNORE INTO notified VALUES (?, ?, ?, ?, ?)",
            (reel_id, page_id, views, link, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()


def parse_fb_time(value):
    if not value:
        return None
    # Graph API returns e.g. "2026-10-17T08:00:00+0000"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


def reel_link(reel):
    link = reel.get("permalink_url") or f"/reel/{reel['id']}"
    if link.startswith("/"):
        link = "https://www.facebook.com" + link
    return link


def format_message(page_name, reel, views, threshold):
    caption = (reel.get("description") or "").strip()
    if len(caption) > 120:
        caption = caption[:117] + "..."
    lines = [
        f"🔥 Reel vượt {threshold:,} view",
        f"Page: {page_name}",
        f"Views: {views:,}",
    ]
    if caption:
        lines.append(f"Caption: {caption}")
    lines.append(reel_link(reel))
    return "\n".join(lines)


def resolve_pages(cfg, graph):
    """Return a list of (page_id, page_name, page_token)."""
    user_tokens = {}
    if cfg["user_access_token"]:
        user_tokens = graph.page_tokens_from_user_token(cfg["user_access_token"])
    pages = []
    for page in cfg["pages"]:
        page_id = str(page["id"])
        token = page.get("access_token") or user_tokens.get(page_id)
        if not token:
            log.warning(
                "No access token for Page %s: you must be an admin of it "
                "(or set 'access_token' for it in the config). Skipping.",
                page_id,
            )
            continue
        pages.append((page_id, page.get("name") or page_id, token))
    return pages


def scan_once(cfg, graph, telegram, store, pages):
    since = datetime.now(timezone.utc) - timedelta(days=cfg["max_reel_age_days"])
    threshold = cfg["view_threshold"]
    sent = 0
    for page_id, page_name, token in pages:
        try:
            reels = graph.recent_reels(page_id, token, since)
        except (GraphAPIError, requests.RequestException) as e:
            log.error("Could not list Reels for %s: %s", page_name, e)
            continue
        log.info("%s: %d recent Reels", page_name, len(reels))
        for reel in reels:
            if store.was_notified(reel["id"]):
                continue
            try:
                views = graph.reel_views(reel["id"], token, cfg["view_metrics"])
            except requests.RequestException as e:
                log.error("Could not read views for Reel %s: %s", reel["id"], e)
                continue
            if views is None:
                log.debug("No view metric for Reel %s", reel["id"])
                continue
            if views >= threshold:
                try:
                    telegram.send(format_message(page_name, reel, views, threshold))
                except (RuntimeError, requests.RequestException) as e:
                    log.error("Telegram send failed for Reel %s: %s", reel["id"], e)
                    continue
                store.mark_notified(reel["id"], page_id, views, reel_link(reel))
                sent += 1
                log.info("Notified Reel %s (%d views)", reel["id"], views)
    return sent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test message")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = load_config(args.config)
    telegram = Telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"])
    if args.test_telegram:
        telegram.send("✅ Reels tracker: kết nối Telegram thành công!")
        log.info("Test message sent")
        return 0

    graph = GraphClient(cfg["graph_api_version"])
    store = Store(Path(cfg["db_path"]))
    pages = resolve_pages(cfg, graph)
    if not pages:
        log.error("No Pages with a usable access token. Nothing to do.")
        return 1

    while True:
        scan_once(cfg, graph, telegram, store, pages)
        if args.once:
            return 0
        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    sys.exit(main())
