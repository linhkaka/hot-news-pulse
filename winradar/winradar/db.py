import json
import sqlite3
import threading
import time

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS ads (
    ad_id TEXT PRIMARY KEY,
    collation_id TEXT,
    collation_count INTEGER DEFAULT 1,
    page_id TEXT,
    page_name TEXT,
    start_ts INTEGER,
    end_ts INTEGER,
    is_active INTEGER,
    title TEXT,
    body TEXT,
    link_url TEXT,
    domain TEXT,
    thumb_url TEXT,
    thumb_path TEXT,
    video_url TEXT,
    dhash TEXT,
    keyword TEXT,
    first_seen INTEGER,
    last_seen INTEGER
);
CREATE INDEX IF NOT EXISTS ads_page ON ads(page_id);
CREATE TABLE IF NOT EXISTS landings (
    url TEXT PRIMARY KEY,
    final_url TEXT,
    domain TEXT,
    platform TEXT,
    created_ts INTEGER,
    published_ts INTEGER,
    title TEXT,
    price TEXT,
    checked_ts INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS videos (
    cid TEXT PRIMARY KEY,
    label TEXT,
    sort_key REAL,
    data TEXT
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT,
    target TEXT,
    status TEXT,
    n_ads INTEGER DEFAULT 0,
    started_ts INTEGER,
    finished_ts INTEGER,
    error TEXT
);
"""


def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_ads(ads, keyword=None):
    """Lưu QC. Giữ nguyên ảnh/hash đã tải, cập nhật trạng thái chạy mới nhất."""
    now = int(time.time())
    with _lock, connect() as conn:
        for a in ads:
            conn.execute(
                """INSERT INTO ads (ad_id, collation_id, collation_count, page_id, page_name, start_ts, end_ts,
                       is_active, title, body, link_url, domain, thumb_url, video_url, keyword, first_seen, last_seen)
                   VALUES (:ad_id, :collation_id, :collation_count, :page_id, :page_name, :start_ts, :end_ts,
                       :is_active, :title, :body, :link_url, :domain, :thumb_url, :video_url, :keyword, :now, :now)
                   ON CONFLICT(ad_id) DO UPDATE SET
                       collation_id=excluded.collation_id, collation_count=excluded.collation_count,
                       end_ts=excluded.end_ts, is_active=excluded.is_active,
                       start_ts=MIN(COALESCE(ads.start_ts, excluded.start_ts), COALESCE(excluded.start_ts, ads.start_ts)),
                       thumb_url=COALESCE(excluded.thumb_url, ads.thumb_url),
                       video_url=COALESCE(excluded.video_url, ads.video_url),
                       keyword=COALESCE(ads.keyword, excluded.keyword),
                       last_seen=excluded.last_seen""",
                {**a, "keyword": keyword, "now": now},
            )


def ads_missing_thumbs():
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT ad_id, thumb_url FROM ads WHERE dhash IS NULL AND thumb_url IS NOT NULL")]


def set_thumb(ad_id, path, dhash):
    with _lock, connect() as conn:
        conn.execute("UPDATE ads SET thumb_path=?, dhash=? WHERE ad_id=?", (path, dhash, ad_id))


def all_ads():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM ads")]


def unchecked_landing_urls(max_age_s=3 * 86400):
    cutoff = int(time.time()) - max_age_s
    with connect() as conn:
        rows = conn.execute(
            """SELECT DISTINCT a.link_url FROM ads a LEFT JOIN landings l ON l.url = a.link_url
               WHERE a.link_url IS NOT NULL AND (l.url IS NULL OR l.checked_ts < ?)""", (cutoff,))
        return [r[0] for r in rows]


def save_landing(info):
    with _lock, connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO landings (url, final_url, domain, platform, created_ts, published_ts,
                   title, price, checked_ts, error)
               VALUES (:url, :final_url, :domain, :platform, :created_ts, :published_ts,
                   :title, :price, :checked_ts, :error)""", info)


def landings_by_url():
    with connect() as conn:
        return {r["url"]: dict(r) for r in conn.execute("SELECT * FROM landings")}


def replace_videos(videos):
    with _lock, connect() as conn:
        conn.execute("DELETE FROM videos")
        conn.executemany(
            "INSERT INTO videos (cid, label, sort_key, data) VALUES (?, ?, ?, ?)",
            [(v["cid"], v["label"], v["ads_per_day"], json.dumps(v, ensure_ascii=False)) for v in videos])


def list_videos(label=None):
    with connect() as conn:
        if label:
            rows = conn.execute("SELECT data FROM videos WHERE label=? ORDER BY sort_key DESC", (label,))
        else:
            rows = conn.execute("SELECT data FROM videos ORDER BY sort_key DESC")
        return [json.loads(r[0]) for r in rows]


def get_video(cid):
    with connect() as conn:
        r = conn.execute("SELECT data FROM videos WHERE cid=?", (cid,)).fetchone()
        return json.loads(r[0]) if r else None


def label_counts():
    with connect() as conn:
        return {r[0]: r[1] for r in conn.execute("SELECT label, COUNT(*) FROM videos GROUP BY label")}


def start_scan(kind, target):
    with _lock, connect() as conn:
        cur = conn.execute("INSERT INTO scans (kind, target, status, started_ts) VALUES (?, ?, 'dang chay', ?)",
                           (kind, target, int(time.time())))
        return cur.lastrowid


def finish_scan(scan_id, status, n_ads=0, error=None):
    with _lock, connect() as conn:
        conn.execute("UPDATE scans SET status=?, n_ads=?, finished_ts=?, error=? WHERE id=?",
                     (status, n_ads, int(time.time()), error, scan_id))


def list_scans(limit=50):
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))]
