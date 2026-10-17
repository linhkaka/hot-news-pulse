import json
import sqlite3
import threading
import time
from contextlib import contextmanager

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
    error TEXT,
    date_source TEXT,
    pod_markers TEXT
);
CREATE TABLE IF NOT EXISTS videos (
    cid TEXT PRIMARY KEY,
    label TEXT,
    sort_key REAL,
    data TEXT
);
CREATE TABLE IF NOT EXISTS follows (
    kind TEXT,            -- 'page' (page Facebook) hoặc 'shop' (domain trang bán)
    key TEXT,
    name TEXT,
    added_ts INTEGER,
    last_scan_ts INTEGER,
    PRIMARY KEY (kind, key)
);
CREATE TABLE IF NOT EXISTS watch_keywords (
    keyword TEXT PRIMARY KEY,
    country TEXT,
    added_ts INTEGER,
    last_scan_ts INTEGER
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS social_videos (
    vid TEXT PRIMARY KEY,          -- '<nền tảng>:<id>'
    platform TEXT,                 -- tiktok | tiktok_ads | fb_reels
    item_id TEXT,
    url TEXT,
    author TEXT,
    caption TEXT,
    cover_url TEXT,
    cover_path TEXT,
    video_url TEXT,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    shares INTEGER,
    saves INTEGER,
    created_ts INTEGER,
    duration INTEGER,
    extra TEXT,
    keyword TEXT,
    first_seen INTEGER,
    last_seen INTEGER
);
CREATE TABLE IF NOT EXISTS social_snapshots (
    vid TEXT,
    ts INTEGER,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    shares INTEGER
);
CREATE INDEX IF NOT EXISTS social_snap_vid ON social_snapshots(vid, ts);
CREATE TABLE IF NOT EXISTS social_watch (
    platform TEXT,
    keyword TEXT,
    country TEXT,
    added_ts INTEGER,
    last_scan_ts INTEGER,
    PRIMARY KEY (platform, keyword)
);
CREATE TABLE IF NOT EXISTS rate_events (
    platform TEXT,
    ts INTEGER
);
CREATE INDEX IF NOT EXISTS rate_events_p ON rate_events(platform, ts);
CREATE TABLE IF NOT EXISTS notified (
    kind TEXT,
    key TEXT,
    ts INTEGER,
    PRIMARY KEY (kind, key)
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


@contextmanager
def connect():
    """Mở kết nối, lưu (commit) khi xong hoặc huỷ khi lỗi, và LUÔN đóng kết nối.

    `with sqlite3.connect()` của Python chỉ commit chứ không đóng; trên Windows file CSDL còn mở thì
    bị khoá (không xoá/đổi tên được), nên phải tự đóng.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


# Cột thêm ở các bản sau: CSDL cũ được nâng cấp tự động, không mất dữ liệu
_MIGRATIONS = [("landings", "date_source", "TEXT"), ("landings", "pod_markers", "TEXT")]


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, col, typ in _MIGRATIONS:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


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
                   title, price, checked_ts, error, date_source, pod_markers)
               VALUES (:url, :final_url, :domain, :platform, :created_ts, :published_ts,
                   :title, :price, :checked_ts, :error, :date_source, :pod_markers)""",
            {"date_source": None, "pod_markers": None, **info})


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


# ---- theo dõi page / shop ----

def add_follow(kind, key, name=None):
    with _lock, connect() as conn:
        conn.execute("INSERT OR IGNORE INTO follows (kind, key, name, added_ts) VALUES (?, ?, ?, ?)",
                     (kind, key, name, int(time.time())))


def remove_follow(kind, key):
    with _lock, connect() as conn:
        conn.execute("DELETE FROM follows WHERE kind=? AND key=?", (kind, key))


def list_follows():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM follows ORDER BY added_ts DESC")]


def touch_follow(kind, key):
    with _lock, connect() as conn:
        conn.execute("UPDATE follows SET last_scan_ts=? WHERE kind=? AND key=?", (int(time.time()), kind, key))


# ---- từ khoá tự quét ----

def add_watch_keyword(keyword, country):
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO watch_keywords (keyword, country, added_ts, last_scan_ts) "
                     "VALUES (?, ?, ?, (SELECT last_scan_ts FROM watch_keywords WHERE keyword=?))",
                     (keyword, country, int(time.time()), keyword))


def remove_watch_keyword(keyword):
    with _lock, connect() as conn:
        conn.execute("DELETE FROM watch_keywords WHERE keyword=?", (keyword,))


def list_watch_keywords():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM watch_keywords ORDER BY keyword")]


def touch_watch_keyword(keyword):
    with _lock, connect() as conn:
        conn.execute("UPDATE watch_keywords SET last_scan_ts=? WHERE keyword=?", (int(time.time()), keyword))


# ---- cài đặt ----

def get_setting(key, default=None):
    with connect() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default


def set_setting(key, value):
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))


# ---- thống kê theo shop / page ----

def ads_where(column, value):
    assert column in ("page_id", "domain")
    with connect() as conn:
        return [dict(r) for r in conn.execute(f"SELECT * FROM ads WHERE {column}=?", (value,))]


def shop_rows():
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT a.domain, COUNT(*) AS ads, SUM(a.is_active) AS active, MIN(a.start_ts) AS first_ts,
                      MAX(a.start_ts) AS last_ts, COUNT(DISTINCT a.page_id) AS pages,
                      MAX(l.platform) AS platform, MAX(l.pod_markers) AS pod_markers
               FROM ads a LEFT JOIN landings l ON l.url = a.link_url
               WHERE a.domain IS NOT NULL GROUP BY a.domain ORDER BY active DESC, ads DESC""")]


# ---- video viral (TikTok / Facebook Reels) ----

def upsert_social(items, keyword=None, now=None):
    """Lưu video + 1 bản chụp số liệu (để tính tốc độ tăng thật giữa các lần quét)."""
    now = now or int(time.time())
    with _lock, connect() as conn:
        for it in items:
            conn.execute(
                """INSERT INTO social_videos (vid, platform, item_id, url, author, caption, cover_url, video_url,
                       views, likes, comments, shares, saves, created_ts, duration, extra, keyword, first_seen, last_seen)
                   VALUES (:vid, :platform, :item_id, :url, :author, :caption, :cover_url, :video_url,
                       :views, :likes, :comments, :shares, :saves, :created_ts, :duration, :extra, :keyword, :now, :now)
                   ON CONFLICT(vid) DO UPDATE SET
                       url=COALESCE(excluded.url, social_videos.url),
                       caption=COALESCE(excluded.caption, social_videos.caption),
                       cover_url=COALESCE(excluded.cover_url, social_videos.cover_url),
                       video_url=COALESCE(excluded.video_url, social_videos.video_url),
                       views=COALESCE(excluded.views, social_videos.views),
                       likes=COALESCE(excluded.likes, social_videos.likes),
                       comments=COALESCE(excluded.comments, social_videos.comments),
                       shares=COALESCE(excluded.shares, social_videos.shares),
                       saves=COALESCE(excluded.saves, social_videos.saves),
                       created_ts=COALESCE(social_videos.created_ts, excluded.created_ts),
                       extra=COALESCE(excluded.extra, social_videos.extra),
                       keyword=COALESCE(social_videos.keyword, excluded.keyword),
                       last_seen=excluded.last_seen""",
                {**it, "keyword": keyword, "now": now})
            conn.execute("INSERT INTO social_snapshots (vid, ts, views, likes, comments, shares) VALUES (?, ?, ?, ?, ?, ?)",
                         (it["vid"], now, it.get("views"), it.get("likes"), it.get("comments"), it.get("shares")))


def social_rows(platform=None):
    with connect() as conn:
        if platform:
            return [dict(r) for r in conn.execute("SELECT * FROM social_videos WHERE platform=?", (platform,))]
        return [dict(r) for r in conn.execute("SELECT * FROM social_videos")]


def social_row(vid):
    with connect() as conn:
        r = conn.execute("SELECT * FROM social_videos WHERE vid=?", (vid,)).fetchone()
        return dict(r) if r else None


def social_snapshots(vids=None):
    """{vid: [(ts, views, likes, comments, shares), ...]} theo thời gian tăng dần."""
    out = {}
    with connect() as conn:
        rows = conn.execute("SELECT vid, ts, views, likes, comments, shares FROM social_snapshots ORDER BY ts")
        for r in rows:
            if vids is None or r[0] in vids:
                out.setdefault(r[0], []).append(tuple(r[1:]))
    return out


def social_missing_covers():
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT vid, platform, cover_url FROM social_videos WHERE cover_path IS NULL AND cover_url IS NOT NULL")]


def set_social_cover(vid, path):
    with _lock, connect() as conn:
        conn.execute("UPDATE social_videos SET cover_path=? WHERE vid=?", (path, vid))


def add_social_watch(platform, keyword, country):
    with _lock, connect() as conn:
        conn.execute("INSERT OR IGNORE INTO social_watch (platform, keyword, country, added_ts) VALUES (?, ?, ?, ?)",
                     (platform, keyword, country, int(time.time())))


def remove_social_watch(platform, keyword):
    with _lock, connect() as conn:
        conn.execute("DELETE FROM social_watch WHERE platform=? AND keyword=?", (platform, keyword))


def list_social_watch():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM social_watch ORDER BY platform, keyword")]


def touch_social_watch(platform, keyword):
    with _lock, connect() as conn:
        conn.execute("UPDATE social_watch SET last_scan_ts=? WHERE platform=? AND keyword=?",
                     (int(time.time()), platform, keyword))


# ---- chế độ an toàn: nhật ký lượt quét theo nền tảng ----

def add_rate_event(platform, ts=None):
    with _lock, connect() as conn:
        conn.execute("INSERT INTO rate_events (platform, ts) VALUES (?, ?)", (platform, ts or int(time.time())))


def count_rate_events(platform, since):
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM rate_events WHERE platform=? AND ts>=?", (platform, since)).fetchone()[0]


def last_rate_event(platform):
    with connect() as conn:
        return conn.execute("SELECT MAX(ts) FROM rate_events WHERE platform=?", (platform,)).fetchone()[0]


# ---- thông báo: nhớ cái đã báo ----

def unseen_notified(kind, keys):
    if not keys:
        return []
    with connect() as conn:
        seen = set()
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            q = "SELECT key FROM notified WHERE kind=? AND key IN (%s)" % ",".join("?" * len(chunk))
            seen |= {r[0] for r in conn.execute(q, [kind, *chunk])}
    return [k for k in keys if k not in seen]


def mark_notified(kind, keys):
    now = int(time.time())
    with _lock, connect() as conn:
        conn.executemany("INSERT OR IGNORE INTO notified (kind, key, ts) VALUES (?, ?, ?)", [(kind, k, now) for k in keys])


def ads_first_seen_since(column, value, since):
    assert column in ("page_id", "domain")
    with connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM ads WHERE {column}=? AND first_seen>=?", (value, since)).fetchone()[0]
