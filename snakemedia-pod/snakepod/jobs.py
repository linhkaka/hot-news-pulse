"""Hàng đợi việc chạy nền (quét, đào sâu) + nhật ký hiển thị trên giao diện."""
import collections
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

import httpx

from . import analyze, config, db, landing, notify, safety
from .imagehash import dhash

LOG = collections.deque(maxlen=300)
_queue = queue.Queue()
_state = {"current": None, "pending": [], "stop": False}


def log(msg):
    LOG.append({"ts": int(time.time()), "msg": msg})
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def status():
    return {"current": _state["current"], "pending": list(_state["pending"]), "log": list(LOG)[-80:],
            "blocked": safety.blocked()}


def submit(kind, title, fn):
    """Xếp việc vào hàng đợi. Bỏ qua nếu việc trùng tên đang chờ/đang chạy."""
    if title in _state["pending"] or title == _state["current"]:
        return False
    _state["pending"].append(title)
    _queue.put((kind, title, fn))
    return True


def stop_current():
    _state["stop"] = True


def _worker():
    while True:
        kind, title, fn = _queue.get()
        _state["pending"].remove(title)
        _state["current"] = title
        _state["stop"] = False
        scan_id = db.start_scan(kind, title)
        try:
            n = fn() or 0
            db.finish_scan(scan_id, "xong" if not _state["stop"] else "da dung", n)
            log(f"Xong: {title}")
        except safety.Skipped as e:
            db.finish_scan(scan_id, "bo qua", error=str(e)[:500])
            log(f"Bỏ qua '{title}': {e}")
        except safety.CheckpointError as e:
            safety.block(e.platform, e.reason, e.url)
            db.finish_scan(scan_id, "checkpoint", error=e.reason)
            log(f"⚠ {e.reason}. ĐÃ TẠM DỪNG mọi lượt quét {safety.PLATFORMS[e.platform]}. "
                "Hãy tự xác minh trên trình duyệt rồi bấm 'Đã xử lý, quét tiếp'.")
        except Exception as e:
            db.finish_scan(scan_id, "loi", error=str(e)[:500])
            log(f"Lỗi khi chạy '{title}': {e}")
        _state["current"] = None


def start_worker():
    threading.Thread(target=_worker, daemon=True).start()
    threading.Thread(target=_scheduler, daemon=True).start()


def should_stop():
    return _state["stop"]


# ---- các bước xử lý sau khi có QC ----

def _parallel(items, work, noun):
    """Chạy `work(item)` cho nhiều item cùng lúc (HTTP_WORKERS luồng), báo tiến độ, dừng được giữa chừng."""
    done = 0
    with ThreadPoolExecutor(max_workers=config.HTTP_WORKERS) as pool:
        futures = [pool.submit(work, it) for it in items]
        for fut in as_completed(futures):
            done += 1
            if should_stop():
                for f in futures:
                    f.cancel()
                return
            err = fut.exception()
            if err:
                log(f"  bỏ qua 1 {noun}: {err}")
            if done % 50 == 0:
                log(f"  ... {done}/{len(items)} {noun}")


def fetch_thumbs():
    todo = db.ads_missing_thumbs()
    if not todo:
        return
    log(f"Tải {len(todo)} ảnh thumbnail để nhận diện video trùng")
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20, follow_redirects=True) as c:
        def work(a):
            r = c.get(a["thumb_url"])
            r.raise_for_status()
            path = config.THUMB_DIR / f"{a['ad_id']}.jpg"
            path.write_bytes(r.content)
            db.set_thumb(a["ad_id"], path.name, dhash(r.content))
        _parallel(todo, work, "ảnh")


def check_landings():
    urls = db.unchecked_landing_urls()
    if not urls:
        return
    log(f"Đọc tuổi {len(urls)} trang bán")
    # Mỗi shop tối đa 2 yêu cầu cùng lúc để không làm phiền / bị shop chặn
    per_domain = collections.defaultdict(lambda: threading.Semaphore(2))
    lock = threading.Lock()
    with httpx.Client(headers={"User-Agent": landing.UA}, follow_redirects=True, timeout=20,
                      limits=httpx.Limits(max_connections=config.HTTP_WORKERS * 2)) as c:
        def work(u):
            with lock:
                sem = per_domain[urlparse(u).netloc]
            with sem:
                db.save_landing(landing.check(u, c))
        _parallel(urls, work, "trang bán")


def recompute():
    videos = analyze.build_videos(db.all_ads(), db.landings_by_url())
    db.replace_videos(videos)
    log(f"Đã chấm lại {len(videos)} video")
    notify.check_videos(videos, log)


def process_after_scan():
    fetch_thumbs()
    check_landings()
    recompute()


def keyword_job(keyword, country, max_ads):
    from . import scraper

    def run():
        log(f"Quét từ khoá '{keyword}' ({country})")
        safety.before_scan("facebook", log, should_stop)
        ads = scraper.scan_keyword(keyword, country, max_ads, log, should_stop)
        log(f"Đọc được {len(ads)} QC")
        db.upsert_ads(ads, keyword)
        db.touch_watch_keyword(keyword)
        process_after_scan()
        return len(ads)
    return run


def follow_job(kind, key, country):
    """Quét lại 1 page (mọi QC video của page) hoặc 1 shop (tìm domain trong thư viện QC)."""
    from . import scraper

    def run():
        safety.before_scan("facebook", log, should_stop)
        started = int(time.time())
        if kind == "page":
            ads = scraper.scan_pages([key], country, config.DIG_MAX_ADS_PER_PAGE, log, should_stop)
        else:
            log(f"Quét shop {key}")
            ads = scraper.scan_keyword(key, country, config.DEFAULT_MAX_ADS, log, should_stop)
            ads = [a for a in ads if a.get("domain") == key] or ads
        log(f"Đọc được {len(ads)} QC")
        db.upsert_ads(ads)
        db.touch_follow(kind, key)
        process_after_scan()
        new = db.ads_first_seen_since("page_id" if kind == "page" else "domain", key, started)
        if new:
            name = next((f["name"] for f in db.list_follows() if f["kind"] == kind and f["key"] == key), None) or key
            log(f"{name}: {new} QC mới")
            notify.follow_update(name, new, log)
        return len(ads)
    return run


def fetch_social_covers():
    todo = db.social_missing_covers()
    if not todo:
        return
    log(f"Tải {len(todo)} ảnh bìa video")
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": landing.UA}
    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as c:
        def work(v):
            ref = {"tiktok": "https://www.tiktok.com/", "tiktok_ads": "https://ads.tiktok.com/",
                   "fb_reels": "https://www.facebook.com/"}.get(v["platform"])
            r = c.get(v["cover_url"], headers={"Referer": ref} if ref else None)
            r.raise_for_status()
            name = "s_" + "".join(ch if ch.isalnum() else "_" for ch in v["vid"]) + ".jpg"
            (config.THUMB_DIR / name).write_bytes(r.content)
            db.set_social_cover(v["vid"], name)
        _parallel(todo, work, "ảnh bìa")


def social_job(platform, keyword, country, max_items, period=7):
    """Quét video viral 1 nền tảng theo từ khoá (Top Ads: từ khoá có thể bỏ trống)."""
    from . import scraper, social

    def run():
        name = social.PLATFORMS[platform]
        log(f"Quét {name} '{keyword or 'tất cả'}' ({country})")
        safety.before_scan(safety.platform_of(platform), log, should_stop)
        items = scraper.scan_social(platform, keyword, country, max_items, period, log, should_stop)
        log(f"Đọc được {len(items)} video {name}")
        db.upsert_social(items, keyword or None)
        db.touch_social_watch(platform, keyword)
        fetch_social_covers()
        vids = {it["vid"] for it in items}
        snaps = db.social_snapshots(vids)
        notify.check_social([social.summarize(r, snaps.get(r["vid"], [])) for r in db.social_rows(platform)
                             if r["vid"] in vids], log)
        return len(items)
    return run


def queue_all_watched(reason):
    """Xếp hàng quét lại mọi từ khoá đã lưu và mọi page/shop đang theo dõi."""
    country = config.DEFAULT_COUNTRY
    n = 0
    for w in db.list_watch_keywords():
        n += submit("keyword", f"Quét '{w['keyword']}'",
                    keyword_job(w["keyword"], w["country"] or country, config.DEFAULT_MAX_ADS))
    for f in db.list_follows():
        n += submit("follow", f"Theo dõi {f['kind']} {f['name'] or f['key']}", follow_job(f["kind"], f["key"], country))
    for w in db.list_social_watch():
        n += submit("social", f"Viral {w['platform']} '{w['keyword']}'",
                    social_job(w["platform"], w["keyword"], w["country"] or country, config.DEFAULT_MAX_ADS))
    log(f"{reason}: xếp {n} việc quét")
    return n


def auto_settings():
    return {"enabled": True, "hour": config.AUTO_SCAN_HOUR, "last_date": None, **db.get_setting("auto", {})}


def scheduler_tick(now=None):
    """Tới giờ tự quét (mặc định 1h sáng) và hôm nay chưa quét -> xếp hàng quét. Trả về True nếu đã xếp."""
    s = auto_settings()
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    if s["enabled"] and now.hour == int(s["hour"]) and s["last_date"] != today:
        db.set_setting("auto", {**s, "last_date": today})
        queue_all_watched(f"Tự quét lúc {s['hour']}h")
        return True
    return False


def _scheduler():
    """Mỗi 30 giây kiểm tra giờ tự quét. Tool phải đang mở."""
    while True:
        try:
            scheduler_tick()
        except Exception as e:
            log(f"Lỗi lịch tự quét: {e}")
        time.sleep(30)


def dig_job(cid, country):
    """Đào sâu: soi toàn bộ QC (cả đã tắt) của các page đang chạy video này để tìm mốc sớm nhất."""
    from . import scraper

    def run():
        v = db.get_video(cid)
        if not v:
            log("Không tìm thấy video")
            return 0
        pages = v["page_ids"][: config.DIG_MAX_PAGES]
        log(f"Đào sâu '{v['title'][:50]}' qua {len(pages)} page")
        safety.before_scan("facebook", log, should_stop)
        ads = scraper.scan_pages(pages, country, config.DIG_MAX_ADS_PER_PAGE, log, should_stop)
        db.upsert_ads(ads)
        process_after_scan()
        return len(ads)
    return run
