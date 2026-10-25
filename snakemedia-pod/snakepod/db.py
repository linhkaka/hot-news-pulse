import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager

from . import config

_lock = threading.Lock()
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HEX16 = re.compile(r"^[0-9a-f]{16}$")


def safe_id(value):
    return bool(_SAFE_ID.match(str(value or "")))

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
    PRIMARY KEY (platform, keyword, country)   -- cùng từ khoá có thể theo dõi ở nhiều thị trường
);
CREATE TABLE IF NOT EXISTS trends (
    market TEXT,                   -- thị trường (US, GB, ...)
    name TEXT,                     -- hashtag (không có dấu #)
    rank INTEGER,
    prev_rank INTEGER,             -- thứ hạng lần quét trước
    rank_diff INTEGER,             -- thay đổi hạng do TikTok báo (nếu có)
    views INTEGER,
    posts INTEGER,
    trend TEXT,                    -- JSON [[thời điểm, mức độ], ...]
    first_seen INTEGER,
    last_seen INTEGER,
    PRIMARY KEY (market, name)
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
CREATE TABLE IF NOT EXISTS video_history (
    cid TEXT,                      -- video (đổi tên tự động khi nhóm QC gộp thêm)
    day TEXT,                      -- YYYY-MM-DD (giờ máy)
    pages_active INTEGER,
    shops_active INTEGER,
    shops_win INTEGER,
    scale INTEGER,
    ads_active INTEGER,
    urls INTEGER,
    PRIMARY KEY (cid, day)
);
CREATE TABLE IF NOT EXISTS marks (
    cid TEXT,
    kind TEXT,                     -- 'test' (Video test) | 'hidden' (Đã ẩn)
    ts INTEGER,
    PRIMARY KEY (cid, kind)
);
CREATE TABLE IF NOT EXISTS digs (
    cid TEXT PRIMARY KEY,
    ts INTEGER
);
CREATE TABLE IF NOT EXISTS stores (
    domain TEXT PRIMARY KEY,
    swept_ts INTEGER,
    ads_found INTEGER,
    new_videos INTEGER
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
_MIGRATIONS = [("landings", "date_source", "TEXT"), ("landings", "pod_markers", "TEXT"),
               ("landings", "compare_price", "TEXT"), ("social_videos", "market", "TEXT")]


def init():
    with connect() as conn:
        fresh = not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ads'").fetchone()
        conn.executescript(SCHEMA)
        if fresh:   # CSDL mới tạo: đã đúng bản mới nhất, không cần "chấm lại khi nâng cấp"
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('schema', '2')")
        for table, col, typ in _MIGRATIONS:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        # Bản cũ: từ khoá viral khoá theo (nền tảng, từ khoá) -> thêm thị trường vào khoá, giữ nguyên dữ liệu
        pk = {r[1] for r in conn.execute("PRAGMA table_info(social_watch)") if r[5]}
        if "country" not in pk:
            conn.executescript("""
                ALTER TABLE social_watch RENAME TO social_watch_old;
                CREATE TABLE social_watch (platform TEXT, keyword TEXT, country TEXT, added_ts INTEGER,
                                           last_scan_ts INTEGER, PRIMARY KEY (platform, keyword, country));
                INSERT OR IGNORE INTO social_watch SELECT platform, keyword, COALESCE(country, ''), added_ts, last_scan_ts
                    FROM social_watch_old;
                DROP TABLE social_watch_old;""")
        # Bản 1.x lưu cả nước cho TikTok tìm kiếm / Reels (không chọn được nước) -> đưa về '' để khớp bản mới
        conn.execute("""UPDATE OR IGNORE social_watch SET country='' WHERE country != ''
                        AND platform NOT IN ('tiktok_ads', 'tiktok_trend', 'tiktok_tags')""")
        conn.execute("""DELETE FROM social_watch WHERE country != ''
                        AND platform NOT IN ('tiktok_ads', 'tiktok_trend', 'tiktok_tags')""")


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


def ads_by_ids(ids):
    ids = list(ids)
    with connect() as conn:
        return [dict(r) for r in conn.execute(f"SELECT * FROM ads WHERE ad_id IN ({','.join('?' * len(ids))})", ids)] if ids else []


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
                   title, price, checked_ts, error, date_source, pod_markers, compare_price)
               VALUES (:url, :final_url, :domain, :platform, :created_ts, :published_ts,
                   :title, :price, :checked_ts, :error, :date_source, :pod_markers, :compare_price)""",
            {"date_source": None, "pod_markers": None, "compare_price": None, **info})


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


def update_setting(key, fn, default=None):
    """Đọc - sửa - ghi 1 cài đặt trong 1 lần khoá (2 luồng cùng sửa không mất dữ liệu). fn(giá trị cũ) -> giá trị mới."""
    with _lock, connect() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        value = fn(json.loads(r[0]) if r else default)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))
        return value


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

def upsert_social(items, keyword=None, now=None, market=None):
    """Lưu video + 1 bản chụp số liệu (để tính tốc độ tăng thật giữa các lần quét).
    market: thị trường của nguồn quét (chỉ nguồn chọn được thị trường mới có)."""
    now = now or int(time.time())
    with _lock, connect() as conn:
        for it in items:
            conn.execute(
                """INSERT INTO social_videos (vid, platform, item_id, url, author, caption, cover_url, video_url,
                       views, likes, comments, shares, saves, created_ts, duration, extra, keyword, first_seen, last_seen, market)
                   VALUES (:vid, :platform, :item_id, :url, :author, :caption, :cover_url, :video_url,
                       :views, :likes, :comments, :shares, :saves, :created_ts, :duration, :extra, :keyword, :now, :now,
                       :market)
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
                       market=COALESCE(excluded.market, social_videos.market),
                       last_seen=excluded.last_seen""",
                {**it, "keyword": keyword, "now": now, "market": it.get("market") or market})
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


def remove_social_watch(platform, keyword, country=None):
    """country=None: bỏ theo dõi ở mọi thị trường."""
    with _lock, connect() as conn:
        if country is None:
            conn.execute("DELETE FROM social_watch WHERE platform=? AND keyword=?", (platform, keyword))
        else:
            conn.execute("DELETE FROM social_watch WHERE platform=? AND keyword=? AND country=?", (platform, keyword, country))


def list_social_watch():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM social_watch ORDER BY platform, keyword, country")]


def touch_social_watch(platform, keyword, country=None):
    with _lock, connect() as conn:
        if country is None:
            conn.execute("UPDATE social_watch SET last_scan_ts=? WHERE platform=? AND keyword=?",
                         (int(time.time()), platform, keyword))
        else:
            conn.execute("UPDATE social_watch SET last_scan_ts=? WHERE platform=? AND keyword=? AND country=?",
                         (int(time.time()), platform, keyword, country))


# ---- hashtag xu hướng theo thị trường (TikTok Creative Center) ----

def upsert_trends(market, items, now=None):
    now = now or int(time.time())
    with _lock, connect() as conn:
        for it in items:
            old = conn.execute("SELECT rank, first_seen FROM trends WHERE market=? AND name=?", (market, it["name"])).fetchone()
            conn.execute("INSERT OR REPLACE INTO trends VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (market, it["name"], it.get("rank"), old[0] if old else None, it.get("rank_diff"), it.get("views"),
                          it.get("posts"), json.dumps(it.get("trend") or []), old[1] if old else now, now))


def list_trends(market=None):
    with connect() as conn:
        q, args = "SELECT * FROM trends", ()
        if market:
            q, args = q + " WHERE market=?", (market,)
        rows = [dict(r) for r in conn.execute(q + " ORDER BY market, rank IS NULL, rank, name", args)]
    for r in rows:
        r["trend"] = json.loads(r["trend"] or "[]")
    return rows


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


def mark_interrupted_scans():
    with _lock, connect() as conn:
        conn.execute("UPDATE scans SET status='gian doan', finished_ts=? WHERE status='dang chay'", (int(time.time()),))


def ad_keywords():
    """Mọi từ khoá đã quét ra QC (chữ thường)."""
    with connect() as conn:
        return {r[0].lower() for r in conn.execute("SELECT DISTINCT keyword FROM ads WHERE keyword IS NOT NULL")}


def ads_first_seen_since(column, value, since):
    assert column in ("page_id", "domain")
    with connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM ads WHERE {column}=? AND first_seen>=?", (value, since)).fetchone()[0]


# ---- lịch sử theo dõi mỗi video (chụp 1 lần mỗi ngày, lần chấm sau cùng trong ngày ghi đè) ----

_KEYED = ("video_history", "marks", "digs")


def rekey(videos):
    """Nhóm QC gộp thêm QC mới thì mã video (cid = mã QC nhỏ nhất) có thể đổi. Mã cũ vẫn là 1 QC trong nhóm,
    nên chuyển lịch sử / đánh dấu / đã đào của mã cũ sang mã mới."""
    with _lock, connect() as conn:
        known = set()
        for t in _KEYED:
            known |= {r[0] for r in conn.execute(f"SELECT DISTINCT cid FROM {t}")}
        known |= {r[0] for r in conn.execute("SELECT key FROM notified WHERE kind IN ('sap_win', 'win')")}
        r = conn.execute("SELECT value FROM settings WHERE key='clones'").fetchone()
        clones = json.loads(r[0]) if r else {}
        known |= set(clones)
        moved = False
        for v in videos:
            olds = {a["ad_id"] for a in v["ads"]} & known - {v["cid"]}
            for old in olds:
                for t in _KEYED:
                    conn.execute(f"UPDATE OR IGNORE {t} SET cid=? WHERE cid=?", (v["cid"], old))
                    conn.execute(f"DELETE FROM {t} WHERE cid=?", (old,))
                # đã báo Sắp WIN / Win cho mã cũ thì không báo lại; video đã clone vẫn hiện "Đã clone"
                conn.execute("UPDATE OR IGNORE notified SET key=? WHERE kind IN ('sap_win', 'win') AND key=?", (v["cid"], old))
                conn.execute("DELETE FROM notified WHERE kind IN ('sap_win', 'win') AND key=?", (old,))
                if old in clones:
                    clones.setdefault(v["cid"], clones[old])
                    del clones[old]
                    moved = True
        if moved:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('clones', ?)", (json.dumps(clones),))


def record_history(videos, day):
    with _lock, connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO video_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(v["cid"], day, v["pages_active"], v["shops_active"], v["shops_win"], v["buckets"]["scale"],
              v["ads_active"], v.get("urls_total", 0)) for v in videos])


def history(cids, limit_days=None):
    """{cid: [{day, pages_active, ...}] mới nhất trước}"""
    cids = list(cids)
    out = {c: [] for c in cids}
    if not cids:
        return out
    with connect() as conn:
        for i in range(0, len(cids), 500):
            chunk = cids[i:i + 500]
            q = "SELECT * FROM video_history WHERE cid IN (%s) ORDER BY day DESC" % ",".join("?" * len(chunk))
            for r in conn.execute(q, chunk):
                if limit_days is None or len(out[r["cid"]]) < limit_days:
                    out[r["cid"]].append(dict(r))
    return out


# ---- Video test / Đã ẩn ----

def set_mark(cid, kind, on):
    with _lock, connect() as conn:
        if on:
            conn.execute("INSERT OR REPLACE INTO marks (cid, kind, ts) VALUES (?, ?, ?)", (cid, kind, int(time.time())))
        else:
            conn.execute("DELETE FROM marks WHERE cid=? AND kind=?", (cid, kind))


def marks():
    """{cid: {'test', 'hidden'}}"""
    out = {}
    with connect() as conn:
        for r in conn.execute("SELECT cid, kind FROM marks"):
            out.setdefault(r[0], set()).add(r[1])
    return out


# ---- đào sâu ----

def mark_dug(cid):
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO digs (cid, ts) VALUES (?, ?)", (cid, int(time.time())))


def digs():
    with connect() as conn:
        return {r[0]: r[1] for r in conn.execute("SELECT cid, ts FROM digs")}


# ---- quét store win ----

def save_store_sweep(domain, ads_found, new_videos):
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO stores (domain, swept_ts, ads_found, new_videos) VALUES (?, ?, ?, ?)",
                     (domain, int(time.time()), ads_found, new_videos))


def store_sweeps():
    with connect() as conn:
        return {r["domain"]: dict(r) for r in conn.execute("SELECT * FROM stores")}



# ---- góp kho: xuất / nhập dữ liệu để gộp kho với đồng đội ----

_AD_COLS = ("ad_id", "collation_id", "collation_count", "page_id", "page_name", "start_ts", "end_ts", "is_active",
            "title", "body", "link_url", "domain", "thumb_url", "video_url", "dhash", "keyword", "first_seen", "last_seen")
_LANDING_COLS = ("url", "final_url", "domain", "platform", "created_ts", "published_ts", "title", "price", "checked_ts",
                 "error", "date_source", "pod_markers", "compare_price")


def export_data():
    with connect() as conn:
        ads = [{k: r[k] for k in _AD_COLS} for r in conn.execute("SELECT * FROM ads")]
        lands = [{k: r[k] for k in _LANDING_COLS} for r in conn.execute("SELECT * FROM landings")]
    return {"format": "snakemedia-pod", "version": 1, "exported_ts": int(time.time()), "ads": ads, "landings": lands}


def import_data(data):
    """Gộp dữ liệu người khác xuất ra: QC mới thì thêm, QC đã có thì lấy mốc sớm nhất / trạng thái mới nhất,
    trang bán lấy bản đọc gần nhất. Trả về (số QC mới, số trang bán cập nhật)."""
    if not isinstance(data, dict) or data.get("format") != "snakemedia-pod":
        raise ValueError("File không phải dữ liệu SNAKEMEDIA POD")
    new_ads = new_lands = 0
    with _lock, connect() as conn:
        for a in data.get("ads") or []:
            if not isinstance(a, dict) or not _SAFE_ID.match(str(a.get("ad_id") or "")):
                continue                                 # mã QC lạ (vd chứa "../") -> bỏ, vì mã dùng làm tên file ảnh
            row = {k: a.get(k) for k in _AD_COLS}
            for k in ("link_url", "thumb_url", "video_url"):
                if row.get(k) and not str(row[k]).startswith(("http://", "https://")):
                    row[k] = None
            if row.get("dhash") and not _HEX16.match(str(row["dhash"])):
                row["dhash"] = None
            old = conn.execute("SELECT * FROM ads WHERE ad_id=?", (row["ad_id"],)).fetchone()
            if not old:
                conn.execute(f"INSERT INTO ads ({','.join(_AD_COLS)}) VALUES ({','.join('?' * len(_AD_COLS))})",
                             [row[k] for k in _AD_COLS])
                new_ads += 1
                continue
            starts = [x for x in (old["start_ts"], row["start_ts"]) if x]
            newer = (row["last_seen"] or 0) > (old["last_seen"] or 0)
            conn.execute(
                """UPDATE ads SET start_ts=?, dhash=COALESCE(dhash, ?), thumb_url=COALESCE(thumb_url, ?),
                       video_url=COALESCE(video_url, ?), is_active=?, end_ts=?, last_seen=? WHERE ad_id=?""",
                (min(starts) if starts else None, row["dhash"], row["thumb_url"], row["video_url"],
                 row["is_active"] if newer else old["is_active"], row["end_ts"] if newer else old["end_ts"],
                 max(old["last_seen"] or 0, row["last_seen"] or 0), row["ad_id"]))
        for l in data.get("landings") or []:
            if not isinstance(l, dict) or not str(l.get("url") or "").startswith(("http://", "https://")):
                continue
            old = conn.execute("SELECT checked_ts FROM landings WHERE url=?", (l["url"],)).fetchone()
            if old and (old[0] or 0) >= (l.get("checked_ts") or 0):
                continue
            conn.execute(f"INSERT OR REPLACE INTO landings ({','.join(_LANDING_COLS)}) VALUES "
                         f"({','.join('?' * len(_LANDING_COLS))})", [l.get(k) for k in _LANDING_COLS])
            new_lands += 1
    return new_ads, new_lands
