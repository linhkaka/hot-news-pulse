"""SQLite storage: tracked Pages/channels, settings, seen Reels/videos and sent alerts."""

import sqlite3
import threading
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        # Shared by the scan loop and the Telegram command thread.
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS notified (
                    reel_id TEXT PRIMARY KEY,
                    page_id TEXT,
                    views INTEGER,
                    link TEXT,
                    notified_at TEXT
                );
                CREATE TABLE IF NOT EXISTS pages (
                    page_id TEXT PRIMARY KEY,
                    name TEXT,
                    access_token TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS yt_channels (
                    channel_id TEXT PRIMARY KEY,
                    title TEXT,
                    uploads_playlist TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT
                );
                CREATE TABLE IF NOT EXISTS yt_videos (
                    video_id TEXT PRIMARY KEY,
                    channel_id TEXT,
                    title TEXT,
                    link TEXT,
                    views INTEGER,
                    updated_at TEXT,
                    notified_at TEXT
                );
                CREATE TABLE IF NOT EXISTS reels (
                    reel_id TEXT PRIMARY KEY,
                    page_id TEXT,
                    link TEXT,
                    description TEXT,
                    views INTEGER,
                    updated_at TEXT
                );
                """
            )
            self.conn.commit()

    def _execute(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.fetchall()

    # --- alerts -------------------------------------------------------------

    def was_notified(self, reel_id):
        return bool(self._execute("SELECT 1 FROM notified WHERE reel_id = ?", (reel_id,)))

    def mark_notified(self, reel_id, page_id, views, link):
        self._execute(
            "INSERT OR IGNORE INTO notified VALUES (?, ?, ?, ?, ?)",
            (reel_id, page_id, views, link, _now()),
        )

    def notified_count(self):
        return self._execute("SELECT COUNT(*) FROM notified")[0][0]

    # --- pages --------------------------------------------------------------

    def seed_pages(self, pages):
        """Add Pages from the config file; Pages removed via /remove stay removed."""
        for page in pages:
            self._execute(
                "INSERT OR IGNORE INTO pages (page_id, name, access_token, added_at) "
                "VALUES (?, ?, ?, ?)",
                (str(page["id"]), page.get("name"), page.get("access_token"), _now()),
            )
            if page.get("access_token"):
                self._execute(
                    "UPDATE pages SET access_token = ? WHERE page_id = ?",
                    (page["access_token"], str(page["id"])),
                )

    def add_page(self, page_id, name, access_token=None):
        self._execute(
            "INSERT INTO pages (page_id, name, access_token, active, added_at) "
            "VALUES (?, ?, ?, 1, ?) "
            "ON CONFLICT(page_id) DO UPDATE SET active = 1, name = excluded.name",
            (page_id, name, access_token, _now()),
        )

    def remove_page(self, page_id):
        with self.lock:
            cur = self.conn.execute(
                "UPDATE pages SET active = 0 WHERE page_id = ? AND active = 1", (page_id,)
            )
            self.conn.commit()
            return cur.rowcount > 0

    def set_page_name(self, page_id, name):
        self._execute("UPDATE pages SET name = ? WHERE page_id = ?", (name, page_id))

    def active_pages(self):
        """List of (page_id, name, own access token or None)."""
        return self._execute(
            "SELECT page_id, name, access_token FROM pages WHERE active = 1 ORDER BY added_at"
        )

    # --- settings -----------------------------------------------------------

    def get_setting(self, key, default=None):
        rows = self._execute("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0][0] if rows else default

    def set_setting(self, key, value):
        self._execute(
            "INSERT INTO settings VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    # --- reels --------------------------------------------------------------

    def save_reel(self, reel_id, page_id, link, description, views):
        self._execute(
            "INSERT INTO reels VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(reel_id) DO UPDATE SET views = excluded.views, "
            "updated_at = excluded.updated_at",
            (reel_id, page_id, link, description, views, _now()),
        )

    def top_reels(self, limit=10):
        return self._execute(
            "SELECT r.views, r.link, COALESCE(p.name, r.page_id) FROM reels r "
            "LEFT JOIN pages p ON p.page_id = r.page_id "
            "ORDER BY r.views DESC LIMIT ?",
            (limit,),
        )

    # --- YouTube --------------------------------------------------------------

    def add_channel(self, channel_id, title, uploads_playlist):
        self._execute(
            "INSERT INTO yt_channels VALUES (?, ?, ?, 1, ?) "
            "ON CONFLICT(channel_id) DO UPDATE SET active = 1, title = excluded.title, "
            "uploads_playlist = excluded.uploads_playlist",
            (channel_id, title, uploads_playlist, _now()),
        )

    def remove_channel(self, channel_id):
        with self.lock:
            cur = self.conn.execute(
                "UPDATE yt_channels SET active = 0 WHERE channel_id = ? AND active = 1",
                (channel_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def active_channels(self):
        """List of (channel_id, title, uploads playlist id)."""
        return self._execute(
            "SELECT channel_id, title, uploads_playlist FROM yt_channels "
            "WHERE active = 1 ORDER BY added_at"
        )

    def yt_was_notified(self, video_id):
        return bool(self._execute(
            "SELECT 1 FROM yt_videos WHERE video_id = ? AND notified_at IS NOT NULL", (video_id,)
        ))

    def save_yt_video(self, video_id, channel_id, title, link, views):
        self._execute(
            "INSERT INTO yt_videos (video_id, channel_id, title, link, views, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(video_id) DO UPDATE SET views = excluded.views, "
            "title = excluded.title, updated_at = excluded.updated_at",
            (video_id, channel_id, title, link, views, _now()),
        )

    def mark_yt_notified(self, video_id):
        self._execute("UPDATE yt_videos SET notified_at = ? WHERE video_id = ?", (_now(), video_id))

    def yt_notified_count(self):
        return self._execute("SELECT COUNT(*) FROM yt_videos WHERE notified_at IS NOT NULL")[0][0]

    def top_videos(self, limit=10):
        return self._execute(
            "SELECT v.views, v.link, COALESCE(c.title, v.channel_id) FROM yt_videos v "
            "LEFT JOIN yt_channels c ON c.channel_id = v.channel_id "
            "ORDER BY v.views DESC LIMIT ?",
            (limit,),
        )
