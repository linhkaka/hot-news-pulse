"""Video viral trên TikTok (tự nhiên + Top Ads) và Facebook Reels.

Giống phần QC Facebook: không có "điểm AI". Một video được dán nhãn bằng luật đọc được:
  - lượt xem mỗi giờ (vph): ưu tiên tốc độ THẬT giữa 2 lần quét gần nhất, nếu chưa có thì lấy trung bình
    từ lúc đăng tới giờ;
  - tuổi video;
  - tỉ lệ tương tác (thích + bình luận + chia sẻ) / lượt xem và tỉ lệ chia sẻ.
Ngưỡng nằm trong config.py.

Bộ đọc duyệt toàn bộ cây JSON (như fb_parser) nên chịu được phần lớn các lần nền tảng đổi cấu trúc.
"""
import json
import re
import time

from . import config, pod
from .fb_parser import _loads_many

PLATFORMS = {"tiktok": "TikTok", "tiktok_ads": "TikTok Top Ads", "fb_reels": "Facebook Reels"}
LABELS = {"dang_no": "Đang nổ", "viral": "Viral", "dang_len": "Đang lên", "binh_thuong": "Bình thường",
          "top_ads": "Top Ads"}
HOUR = 3600
# Thẻ <script ... type="application/json" ...> với thuộc tính theo bất kỳ thứ tự nào (TikTok đặt id trước type)
_SCRIPT_RE = re.compile(r'<script\b[^>]*\btype="application/json"[^>]*>(.*?)</script>', re.S)


def _walk(obj):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _int(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, dict):                      # {"count": 123}
        return _int(v.get("count"))
    s = str(v).strip().replace(",", "")
    mult = 1
    if s[-1:].upper() in ("K", "M", "B"):        # "1.2M"
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}[s[-1].upper()]
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def _first(d, *keys, depth=3):
    """Giá trị đầu tiên có khoá trong `keys`, tìm cả trong dict con (tối đa `depth` tầng)."""
    level = [d]
    for _ in range(depth + 1):
        nxt = []
        for cur in level:
            for k in keys:
                if isinstance(cur, dict) and cur.get(k) not in (None, "", {}):
                    return cur[k]
            if isinstance(cur, dict):
                nxt.extend(v for v in cur.values() if isinstance(v, dict))
        level = nxt
    return None


def _text(v):
    if isinstance(v, dict):
        v = v.get("text")
    return v.strip() if isinstance(v, str) and v.strip() else None


def _blobs(text):
    yield from _loads_many(text)


def _html_blobs(html):
    for m in _SCRIPT_RE.finditer(html):
        try:
            yield json.loads(m.group(1))
        except ValueError:
            continue


# ---------------- TikTok tự nhiên ----------------

def tiktok_item(d):
    stats = d.get("stats") if isinstance(d.get("stats"), dict) else None
    if not stats or "playCount" not in stats or not d.get("id"):
        return None
    st2 = d.get("statsV2") if isinstance(d.get("statsV2"), dict) else {}
    pick = lambda k: max(filter(None, [_int(stats.get(k)), _int(st2.get(k))]), default=None)
    raw_author = d.get("author")
    author = raw_author if isinstance(raw_author, dict) else {}
    handle = author.get("uniqueId") or (raw_author if isinstance(raw_author, str) else None)
    video = d.get("video") if isinstance(d.get("video"), dict) else {}
    item_id = str(d["id"])
    return {
        "vid": f"tiktok:{item_id}",
        "platform": "tiktok",
        "item_id": item_id,
        "url": f"https://www.tiktok.com/@{handle or '_'}/video/{item_id}",
        "author": handle or author.get("nickname"),
        "caption": _text(d.get("desc")),
        "cover_url": video.get("cover") or video.get("originCover") or video.get("dynamicCover"),
        "video_url": video.get("playAddr") if isinstance(video.get("playAddr"), str) else None,
        "views": pick("playCount"),
        "likes": pick("diggCount"),
        "comments": pick("commentCount"),
        "shares": pick("shareCount"),
        "saves": pick("collectCount"),
        "created_ts": _int(d.get("createTime")),
        "duration": _int(video.get("duration")),
        "extra": None,
    }


def parse_tiktok_text(text):
    out = {}
    for blob in _blobs(text):
        for d in _walk(blob):
            it = tiktok_item(d)
            if it:
                out[it["vid"]] = it
    return list(out.values())


def parse_tiktok_html(html):
    out = {}
    for blob in _html_blobs(html):
        for d in _walk(blob):
            it = tiktok_item(d)
            if it:
                out[it["vid"]] = it
    return list(out.values())


# ---------------- TikTok Top Ads (Creative Center) ----------------

def topads_item(d):
    if not d.get("ad_title") and not d.get("brand_name"):
        return None
    vi = d.get("video_info")
    if not isinstance(vi, dict) or not d.get("id"):
        return None
    vurl = vi.get("video_url")
    if isinstance(vurl, dict):
        vurl = next(iter(vurl.values()), None)
    item_id = str(d["id"])
    extra = {k: d.get(k) for k in ("brand_name", "ctr", "cost", "industry_key", "objective_key", "landing_page")
             if d.get(k) is not None}
    return {
        "vid": f"tiktok_ads:{item_id}",
        "platform": "tiktok_ads",
        "item_id": item_id,
        "url": f"https://ads.tiktok.com/business/creativecenter/topads/{item_id}/pc/en",
        "author": d.get("brand_name"),
        "caption": _text(d.get("ad_title")),
        "cover_url": vi.get("cover"),
        "video_url": vurl if isinstance(vurl, str) else None,
        "views": None,
        "likes": _int(d.get("like")),
        "comments": _int(d.get("comment")),
        "shares": _int(d.get("share")),
        "saves": None,
        "created_ts": None,
        "duration": _int(vi.get("duration")),
        "extra": json.dumps(extra, ensure_ascii=False) if extra else None,
    }


def parse_topads_text(text):
    out = {}
    for blob in _blobs(text):
        for d in _walk(blob):
            it = topads_item(d)
            if it:
                out[it["vid"]] = it
    return list(out.values())


# ---------------- Facebook Reels (THỬ NGHIỆM) ----------------

def reel_item(d):
    """Node video/reel trong GraphQL của Facebook. Cấu trúc hay đổi -> đọc lỏng tay, thiếu gì để trống."""
    views = _int(d.get("play_count")) or _int(d.get("video_view_count"))
    if views is None or not d.get("id"):
        return None
    item_id = str(d.get("post_id") or d["id"])
    owner = _first(d, "owner", "video_owner", "actor") or {}
    url = _first(d, "permalink_url", "url", "shareable_url")
    created = _int(_first(d, "creation_time", "publish_time", "created_time"))
    cover = _first(d, "preferred_thumbnail", "thumbnailImage", "first_frame_thumbnail", "image")
    if isinstance(cover, dict):
        cover = _first(cover, "uri", "url")
    caption = _text(_first(d, "message", "title", "description", "savable_description"))
    video_url = _first(d, "playable_url", "browser_native_sd_url")
    return {
        "vid": f"fb_reels:{item_id}",
        "platform": "fb_reels",
        "item_id": item_id,
        "url": url if isinstance(url, str) else f"https://www.facebook.com/reel/{item_id}",
        "author": owner.get("name") if isinstance(owner, dict) else None,
        "caption": caption,
        "cover_url": cover if isinstance(cover, str) else None,
        "video_url": video_url if isinstance(video_url, str) else None,
        "views": views,
        "likes": _int(_first(d, "reaction_count", "likers", "unified_reactors")),
        "comments": _int(_first(d, "comment_count", "total_comment_count")),
        "shares": _int(_first(d, "share_count", "reshares")),
        "saves": None,
        "created_ts": created,
        "duration": _int(_first(d, "playable_duration_in_ms", "length_in_second")),
        "extra": None,
    }


def parse_reels_text(text):
    out = {}
    for blob in _blobs(text):
        for d in _walk(blob):
            it = reel_item(d)
            if it:
                out[it["vid"]] = it
    return list(out.values())


def parse_reels_html(html):
    out = {}
    for blob in _html_blobs(html):
        for d in _walk(blob):
            it = reel_item(d)
            if it:
                out[it["vid"]] = it
    return list(out.values())


# ---------------- Chấm điểm ----------------

def _fmt(n):
    if n is None:
        return "?"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            return f"{n / div:.1f}{suf}"
    return str(int(n))


def summarize(row, snapshots, now=None):
    """row: 1 dòng social_videos; snapshots: [(ts, views, likes, comments, shares)] theo thời gian tăng dần."""
    now = now or int(time.time())
    c = config
    v = dict(row)
    v["extra"] = json.loads(row["extra"]) if row.get("extra") else {}
    age_h = (now - row["created_ts"]) / HOUR if row.get("created_ts") else None
    v["age_days"] = round(age_h / 24, 1) if age_h is not None else None
    views = row.get("views")
    v["avg_vph"] = round(views / max(age_h, 1)) if views is not None and age_h else None

    recent = None
    snaps = [s for s in snapshots if s[1] is not None]
    if len(snaps) >= 2:
        (t0, v0, *_), (t1, v1, *_) = snaps[-2], snaps[-1]
        if t1 - t0 >= 600:                       # 2 lần quét cách nhau >= 10 phút
            recent = round(max(0, v1 - v0) / ((t1 - t0) / HOUR))
    v["recent_vph"] = recent
    vph = recent if recent is not None else v["avg_vph"]
    v["vph"] = vph

    inter = sum(x or 0 for x in (row.get("likes"), row.get("comments"), row.get("shares")))
    v["engagement"] = round(100 * inter / views, 2) if views else None
    v["share_rate"] = round(100 * (row.get("shares") or 0) / views, 2) if views else None
    v["snapshots"] = [{"ts": s[0], "views": s[1], "likes": s[2], "comments": s[3], "shares": s[4]}
                      for s in snapshots[-30:]]

    checks = []
    if row["platform"] == "tiktok_ads":
        label = "top_ads"
        ex = v["extra"]
        checks.append({"ok": True, "text": "Nằm trong Top Ads của TikTok Creative Center"})
        if row.get("likes") is not None:
            checks.append({"ok": None, "text": f"{_fmt(row['likes'])} lượt thích"})
        if ex.get("ctr") is not None:
            checks.append({"ok": None, "text": f"CTR: {ex['ctr']}"})
        if ex.get("cost") is not None:
            checks.append({"ok": None, "text": f"Mức ngân sách: {ex['cost']}"})
    else:
        src = "giữa 2 lần quét gần nhất" if recent is not None else "trung bình từ lúc đăng"
        if age_h is None or vph is None:
            checks.append({"ok": None, "text": "Chưa rõ ngày đăng hoặc lượt xem"})
        else:
            checks.append({"ok": None, "text": f"{_fmt(vph)} lượt xem/giờ ({src}), video {age_h / 24:.1f} ngày tuổi"})
        explode = vph is not None and age_h is not None and vph >= c.VIRAL_EXPLODE_VPH and age_h <= c.VIRAL_EXPLODE_MAX_DAYS * 24
        viral = views is not None and age_h is not None and views >= c.VIRAL_MIN_VIEWS and age_h <= c.VIRAL_MAX_DAYS * 24
        rising = vph is not None and age_h is not None and vph >= c.VIRAL_RISING_VPH and age_h <= c.VIRAL_RISING_MAX_DAYS * 24
        checks.append({"ok": explode, "text": f"Đang nổ: ≥ {_fmt(c.VIRAL_EXPLODE_VPH)} xem/giờ và ≤ {c.VIRAL_EXPLODE_MAX_DAYS} ngày"})
        checks.append({"ok": viral, "text": f"Viral: ≥ {_fmt(c.VIRAL_MIN_VIEWS)} xem và ≤ {c.VIRAL_MAX_DAYS} ngày ({_fmt(views)} xem)"})
        checks.append({"ok": rising, "text": f"Đang lên: ≥ {_fmt(c.VIRAL_RISING_VPH)} xem/giờ và ≤ {c.VIRAL_RISING_MAX_DAYS} ngày"})
        label = "dang_no" if explode else "viral" if viral else "dang_len" if rising else "binh_thuong"
        if v["engagement"] is not None:
            checks.append({"ok": None, "text": f"Tương tác {v['engagement']}% · chia sẻ {v['share_rate']}%"})
    v["label"] = label
    v["checks"] = checks

    product_type, niches, personalized = pod.classify(row.get("caption") or "")
    v.update(product_type=product_type, niches=niches, personalized=personalized,
             is_pod=bool(product_type or personalized))
    v["sort_vph"] = vph or 0
    return v
