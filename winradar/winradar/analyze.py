"""Gom QC thành "video" rồi chấm nhãn bằng luật rõ ràng (xem config.py).

Một "video" = nhóm QC dùng chung 1 nội dung, trên mọi page/shop, cả QC đang chạy lẫn đã tắt.
Tuổi video = ngày QC SỚM NHẤT trong nhóm, nên shop có đổi caption/đổi page/lên bài mới
thì cũng không giấu được tuổi thật.
"""
import time
from collections import Counter, defaultdict

from . import config
from .imagehash import distance

DAY = 86400


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def cluster(ads, max_distance=config.DHASH_MAX_DISTANCE):
    """Trả về {cid: [ad, ...]}. Gom theo: cùng collation của Facebook, cùng link video, ảnh gần giống."""
    uf = _UnionFind()
    by_key = defaultdict(list)
    for a in ads:
        uf.find(a["ad_id"])
        if a.get("collation_id"):
            by_key["c:" + a["collation_id"]].append(a["ad_id"])
        if a.get("dhash"):
            by_key["h:" + a["dhash"]].append(a["ad_id"])
    for ids in by_key.values():
        for other in ids[1:]:
            uf.union(ids[0], other)

    # So sánh các hash khác nhau nhưng gần giống (video bị cắt/nén lại)
    hashes = sorted({a["dhash"] for a in ads if a.get("dhash")})
    ints = [int(h, 16) for h in hashes]
    for i in range(len(ints)):
        for j in range(i + 1, len(ints)):
            if (ints[i] ^ ints[j]).bit_count() <= max_distance:
                uf.union(by_key["h:" + hashes[i]][0], by_key["h:" + hashes[j]][0])

    groups = defaultdict(list)
    for a in ads:
        groups[uf.find(a["ad_id"])].append(a)
    return dict(groups)


def _days(ts, now):
    return (now - ts) / DAY if ts else None


def _w(a):
    return a.get("collation_count") or 1


def summarize(cid, ads, landings, now=None):
    now = now or int(time.time())
    starts = [a["start_ts"] for a in ads if a.get("start_ts")]
    first_ts = min(starts) if starts else None
    video_age = _days(first_ts, now)

    active = [a for a in ads if a.get("is_active")]
    inactive = [a for a in ads if not a.get("is_active")]

    buckets = {"scale": 0, "win": 0, "old": 0}
    shop_run = defaultdict(list)     # domain -> số ngày chạy của các QC đang sống
    for a in active:
        run = _days(a.get("start_ts"), now) or 0
        key = "scale" if run < config.SCALE_MAX_DAYS else "win" if run <= config.WIN_MAX_DAYS else "old"
        buckets[key] += _w(a)
        shop_run[a.get("domain") or "?"].append(run)

    pages_all = {a["page_id"] for a in ads if a.get("page_id")}
    pages_active = {a["page_id"] for a in active if a.get("page_id")}
    shops_all = {a["domain"] for a in ads if a.get("domain")}
    shops_active = {a["domain"] for a in active if a.get("domain")}
    shops_win = {d for d, runs in shop_run.items()
                 if d != "?" and any(config.SCALE_MAX_DAYS <= r <= config.WIN_MAX_DAYS for r in runs)}
    shops_new_post = {d for d, runs in shop_run.items() if d != "?" and min(runs) < config.NEW_POST_DAYS}
    ads_total = sum(_w(a) for a in ads)
    ads_per_day = ads_total / max(1.0, video_age or 1.0)

    # Trang bán chính = link có nhiều QC nhất; tuổi trang = trang SỚM nhất trong các trang đã đọc được
    link_counts = Counter(a["link_url"] for a in ads if a.get("link_url"))
    main_link = link_counts.most_common(1)[0][0] if link_counts else None
    main_landing = landings.get(main_link) if main_link else None
    land_ts = [l["created_ts"] for u in link_counts if (l := landings.get(u)) and l.get("created_ts")]
    landing_first_ts = min(land_ts) if land_ts else None
    landing_age = _days(landing_first_ts, now)
    page_old = bool(landing_first_ts and first_ts and
                    first_ts - landing_first_ts > config.PAGE_OLDER_THAN_VIDEO * DAY)

    label, checks = _label(video_age, landing_age, page_old, shops_active, shops_win, buckets)

    rep = max(ads, key=lambda a: (bool(a.get("video_url")), bool(a.get("thumb_path")), a.get("is_active") or 0,
                                  _w(a)))
    title = rep.get("body") or rep.get("title") or (main_landing or {}).get("title") or "(không có nội dung)"
    return {
        "cid": cid,
        "label": label,
        "checks": checks,
        "title": title.split("\n")[0][:300],
        "body": rep.get("body"),
        "thumb": rep.get("thumb_path"),
        "thumb_url": rep.get("thumb_url"),
        "video_url": rep.get("video_url"),
        "ad_library_url": f"https://www.facebook.com/ads/library/?id={rep['ad_id']}",
        "main_link": main_link,
        "price": (main_landing or {}).get("price"),
        "platform": (main_landing or {}).get("platform"),
        "first_ts": first_ts,
        "video_age_days": round(video_age, 1) if video_age is not None else None,
        "landing_created_ts": landing_first_ts,
        "landing_age_days": round(landing_age, 1) if landing_age is not None else None,
        "page_old": page_old,
        "pages_active": len(pages_active),
        "pages_total": len(pages_all),
        "shops_active": len(shops_active),
        "shops_total": len(shops_all),
        "shops_win": len(shops_win),
        "shops_new_post": len(shops_new_post),
        "ads_total": ads_total,
        "ads_active": sum(_w(a) for a in active),
        "ads_gone": sum(_w(a) for a in inactive),
        "ads_per_day": round(ads_per_day, 2),
        "buckets": buckets,
        "page_ids": sorted(pages_all),
        "shops": sorted(shops_all),
        "ads": [{k: a.get(k) for k in ("ad_id", "page_id", "page_name", "domain", "link_url", "start_ts",
                                       "end_ts", "is_active", "collation_count")}
                for a in sorted(ads, key=lambda a: a.get("start_ts") or 0)],
        "keywords": sorted({a["keyword"] for a in ads if a.get("keyword")}),
        "last_seen": max((a.get("last_seen") or 0) for a in ads),
    }


def _label(video_age, landing_age, page_old, shops_active, shops_win, buckets):
    c = config
    checks = []

    def check(ok, text):
        checks.append({"ok": ok, "text": text})
        return ok

    if video_age is None:
        check(False, "Chưa rõ tuổi video")
        video_new = video_ok = False
    else:
        video_new = check(video_age <= c.NEW_VIDEO_DAYS,
                          f"Video {video_age:.0f} ngày tuổi (mới nếu ≤ {c.NEW_VIDEO_DAYS} ngày)")
        video_ok = video_age <= c.OLD_VIDEO_DAYS
    if landing_age is None:
        checks.append({"ok": None, "text": "Chưa đọc được tuổi trang bán"})
    else:
        check(not page_old, f"Trang bán {landing_age:.0f} ngày tuổi"
              + (f" — cũ hơn video quá {c.PAGE_OLDER_THAN_VIDEO} ngày" if page_old else ""))
    many_shops = check(len(shops_active) >= c.MIN_SHOPS_SAP_WIN,
                       f"{len(shops_active)} shop đang chạy (cần ≥ {c.MIN_SHOPS_SAP_WIN})")
    proven = check(len(shops_win) >= c.MIN_SHOPS_WIN,
                   f"{len(shops_win)} shop giữ QC sống {c.SCALE_MAX_DAYS}–{c.WIN_MAX_DAYS} ngày (cần ≥ {c.MIN_SHOPS_WIN})")

    if video_age is not None and not video_ok:
        label = "cu"
    elif page_old:
        label = "trang_cu"
    elif proven and video_ok:
        label = "win"
    elif video_new and many_shops:
        label = "sap_win"
    elif buckets["scale"] >= c.MIN_SCALE_ADS and video_ok:
        label = "scale"
    else:
        label = "theo_doi"
    return label, checks


def build_videos(ads, landings, now=None):
    videos = [summarize(cid, group, landings, now) for cid, group in cluster(ads).items()]
    videos.sort(key=lambda v: v["ads_per_day"], reverse=True)
    return videos
