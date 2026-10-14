"""Hàng đợi việc chạy nền (quét, đào sâu) + nhật ký hiển thị trên giao diện."""
import collections
import queue
import threading
import time
from pathlib import Path

import httpx

from . import analyze, config, db, landing
from .imagehash import dhash

LOG = collections.deque(maxlen=300)
_queue = queue.Queue()
_state = {"current": None, "pending": [], "stop": False}


def log(msg):
    LOG.append({"ts": int(time.time()), "msg": msg})
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def status():
    return {"current": _state["current"], "pending": list(_state["pending"]), "log": list(LOG)[-80:]}


def submit(kind, title, fn):
    _state["pending"].append(title)
    _queue.put((kind, title, fn))


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
        except Exception as e:
            db.finish_scan(scan_id, "loi", error=str(e)[:500])
            log(f"Lỗi khi chạy '{title}': {e}")
        _state["current"] = None


def start_worker():
    threading.Thread(target=_worker, daemon=True).start()


def should_stop():
    return _state["stop"]


# ---- các bước xử lý sau khi có QC ----

def fetch_thumbs():
    todo = db.ads_missing_thumbs()
    if not todo:
        return
    log(f"Tải {len(todo)} ảnh thumbnail để nhận diện video trùng")
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=20, follow_redirects=True) as c:
        for i, a in enumerate(todo):
            if should_stop():
                return
            try:
                r = c.get(a["thumb_url"])
                r.raise_for_status()
                path = config.THUMB_DIR / f"{a['ad_id']}.jpg"
                path.write_bytes(r.content)
                db.set_thumb(a["ad_id"], path.name, dhash(r.content))
            except Exception as e:
                log(f"  bỏ qua ảnh {a['ad_id']}: {e}")
            if i and i % 50 == 0:
                log(f"  ... {i}/{len(todo)} ảnh")


def check_landings():
    urls = db.unchecked_landing_urls()
    if not urls:
        return
    log(f"Đọc tuổi {len(urls)} trang bán")
    with httpx.Client(headers={"User-Agent": landing.UA}, follow_redirects=True, timeout=20) as c:
        for u in urls:
            if should_stop():
                return
            db.save_landing(landing.check(u, c))


def recompute():
    videos = analyze.build_videos(db.all_ads(), db.landings_by_url())
    db.replace_videos(videos)
    log(f"Đã chấm lại {len(videos)} video")


def process_after_scan():
    fetch_thumbs()
    check_landings()
    recompute()


def keyword_job(keyword, country, max_ads):
    from . import scraper

    def run():
        log(f"Quét từ khoá '{keyword}' ({country})")
        ads = scraper.scan_keyword(keyword, country, max_ads, log, should_stop)
        log(f"Đọc được {len(ads)} QC")
        db.upsert_ads(ads, keyword)
        process_after_scan()
        return len(ads)
    return run


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
        ads = scraper.scan_pages(pages, country, config.DIG_MAX_ADS_PER_PAGE, log, should_stop)
        db.upsert_ads(ads)
        process_after_scan()
        return len(ads)
    return run
