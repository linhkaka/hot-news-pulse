"""Hàng đợi việc chạy nền (quét, đào sâu) + nhật ký hiển thị trên giao diện."""
import collections
import os
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
_state = {"current": None, "pending": [], "stop": False, "kind": None, "started": None, "count": 0}
# Phiên quét: các việc đã xong kể từ lúc hàng đợi rảnh -> bảng tiến độ "đang quét 9 / 25"
SESSION = collections.deque(maxlen=200)
EST_JOB_S = 120                 # ước lượng 1 việc khi chưa có việc nào xong (giây)


def log(msg):
    LOG.append({"ts": int(time.time()), "msg": msg})
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def set_progress(n):
    """Số QC / video đã đọc của việc đang chạy (bộ quét gọi mỗi lần đọc thêm)."""
    _state["count"] = int(n)


def progress(now=None):
    """Tiến độ phiên quét: việc xong (kèm số QC, thời gian), việc đang chạy, tốc độ QC/phút, thời gian còn lại."""
    now = now or time.time()
    done = list(SESSION)
    cur = None
    if _state["current"]:
        cur = {"title": _state["current"], "kind": _state["kind"], "count": _state["count"],
               "secs": int(now - (_state["started"] or now))}
    items = sum(d["n"] for d in done) + (cur["count"] if cur else 0)
    secs = sum(d["secs"] for d in done) + (cur["secs"] if cur else 0)
    avg = (sum(d["secs"] for d in done) / len(done)) if done else EST_JOB_S
    left = len(_state["pending"]) * avg + (max(0, avg - cur["secs"]) if cur else 0)
    return {"done": done[-30:], "n_done": len(done), "current": cur, "pending": list(_state["pending"]),
            "total": len(done) + (1 if cur else 0) + len(_state["pending"]), "items": items,
            "rate": round(items * 60 / secs) if secs >= 30 else None,
            "eta_s": int(left) if (cur or _state["pending"]) else 0}


def status():
    return {"current": _state["current"], "pending": list(_state["pending"]), "log": list(LOG)[-80:],
            "blocked": safety.blocked(), "progress": progress()}


def submit(kind, title, fn):
    """Xếp việc vào hàng đợi. Bỏ qua nếu việc trùng tên đang chờ/đang chạy."""
    if title in _state["pending"] or title == _state["current"]:
        return False
    if not _state["current"] and not _state["pending"]:   # hàng đợi đang rảnh -> bắt đầu phiên mới
        SESSION.clear()
    _state["pending"].append(title)
    _queue.put((kind, title, fn))
    return True


def stop_current():
    _state["stop"] = True


def _run(kind, title, fn):
    """Chạy 1 việc, ghi kết quả vào lịch sử quét. Trả về (số QC / video, trạng thái)."""
    scan_id = db.start_scan(kind, title)
    try:
        n = fn() or 0
        st = "xong" if not _state["stop"] else "da dung"
        db.finish_scan(scan_id, st, n)
        log(f"Xong: {title}")
        return n, st
    except safety.Skipped as e:
        db.finish_scan(scan_id, "bo qua", error=str(e)[:500])
        log(f"Bỏ qua '{title}': {e}")
        return 0, "bo qua"
    except safety.CheckpointError as e:
        safety.block(e.platform, e.reason, e.url)
        db.finish_scan(scan_id, "checkpoint", error=e.reason)
        log(f"⚠ {e.reason}. ĐÃ TẠM DỪNG mọi lượt quét {safety.PLATFORMS[e.platform]}. "
            "Hãy tự xác minh trên trình duyệt rồi bấm 'Đã xử lý, quét tiếp'.")
        return 0, "checkpoint"
    except Exception as e:
        db.finish_scan(scan_id, "loi", error=str(e)[:500])
        log(f"Lỗi khi chạy '{title}': {e}")
        return 0, "loi"


def _worker():
    while True:
        kind, title, fn = _queue.get()
        if title in _state["pending"]:
            _state["pending"].remove(title)
        _state.update(current=title, kind=kind, stop=False, started=time.time(), count=0)
        n, st = 0, "loi"
        try:
            n, st = _run(kind, title, fn)
        except Exception as e:      # lỗi ghi cơ sở dữ liệu (đĩa đầy, file bị khoá...): báo rồi chạy việc tiếp theo
            log(f"Lỗi khi chạy '{title}': {e}")
        finally:
            SESSION.append({"title": title, "kind": kind, "n": int(n), "status": st,
                            "secs": int(time.time() - (_state["started"] or time.time())), "ts": int(time.time())})
            _state.update(current=None, kind=None, count=0)


def start_worker():
    threading.Thread(target=_worker, daemon=True).start()
    if os.environ.get("SNAKEPOD_NO_SCHEDULER") != "1":   # bài kiểm thử tắt lịch để không phụ thuộc giờ chạy
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
    todo = [a for a in db.ads_missing_thumbs() if db.safe_id(a["ad_id"])]   # mã QC làm tên file: chỉ chữ / số
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
    db.rekey(videos)
    db.record_history(videos, datetime.now().strftime("%Y-%m-%d"))
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
        ads = scraper.scan_keyword(keyword, country, max_ads, log, should_stop, set_progress)
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
            ads = scraper.scan_pages([key], country, config.DIG_MAX_ADS_PER_PAGE, log, should_stop, set_progress)
        else:
            log(f"Quét shop {key}")
            ads = scraper.scan_keyword(key, country, config.DEFAULT_MAX_ADS, log, should_stop, set_progress)
            ads = [a for a in ads if a.get("domain") == key]       # chỉ QC dẫn về đúng shop
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
                   "tiktok_trend": "https://ads.tiktok.com/", "fb_reels": "https://www.facebook.com/"}.get(v["platform"])
            r = c.get(v["cover_url"], headers={"Referer": ref} if ref else None)
            r.raise_for_status()
            name = "s_" + "".join(ch if ch.isalnum() else "_" for ch in v["vid"]) + ".jpg"
            (config.THUMB_DIR / name).write_bytes(r.content)
            db.set_social_cover(v["vid"], name)
        _parallel(todo, work, "ảnh bìa")


def follow_title(kind, key, name=None):
    """Tên việc theo dõi; 2 page trùng tên vẫn là 2 việc khác nhau (hàng đợi bỏ việc trùng tên)."""
    return f"Theo dõi {kind} {name}" + (f" ({key})" if name and name != key else "") if name else f"Theo dõi {kind} {key}"


def social_title(platform, keyword, country):
    from . import social
    return f"Viral {platform} '{keyword}'" + (f" {country}" if platform in social.MARKET_SOURCES else "")


def social_job(platform, keyword, country, max_items, period=7):
    """Quét video viral 1 nguồn theo từ khoá / hashtag (Top Ads, thịnh hành, hashtag xu hướng: từ khoá có thể bỏ trống).
    Nguồn Creative Center quét đúng thị trường `country`; TikTok tìm kiếm / Reels theo tài khoản + IP của bạn."""
    from . import scraper, social

    def run():
        name = social.SOURCES[platform]
        by_market = platform in social.MARKET_SOURCES
        log(f"Quét {name} '{keyword or 'tất cả'}'" + (f" ({country})" if by_market else ""))
        safety.before_scan(safety.platform_of(platform), log, should_stop)
        items = scraper.scan_social(platform, keyword, country, max_items, period, log, should_stop, set_progress)
        db.touch_social_watch(platform, keyword, country if by_market else "")
        if platform == "tiktok_tags":
            db.upsert_trends(country, items)
            log(f"Đọc được {len(items)} hashtag xu hướng ({country})")
            return len(items)
        log(f"Đọc được {len(items)} video {name}")
        db.upsert_social(items, keyword or None, market=country if by_market else None)
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
        n += submit("follow", follow_title(f["kind"], f["key"], f["name"]), follow_job(f["kind"], f["key"], country))
    for w in db.list_social_watch():
        c = w["country"] or country
        n += submit("social", social_title(w["platform"], w["keyword"], c),
                    social_job(w["platform"], w["keyword"], c, config.DEFAULT_MAX_ADS))
    n_stores = int(auto_settings().get("stores", config.AUTO_SWEEP_STORES))
    n += queue_sweeps([r["domain"] for r in store_rows() if r["status"] == "pending"][:n_stores], country)
    log(f"{reason}: xếp {n} việc quét")
    return n


def auto_settings():
    return {"enabled": True, "hour": config.AUTO_SCAN_HOUR, "stores": config.AUTO_SWEEP_STORES, "last_date": None,
            **db.get_setting("auto", {})}


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
        ads = scraper.scan_pages(pages, country, config.DIG_MAX_ADS_PER_PAGE, log, should_stop, set_progress)
        db.upsert_ads(ads)
        db.mark_dug(cid)
        process_after_scan()
        return len(ads)
    return run


def dig_candidates():
    """Video Sắp WIN / Tiềm năng chưa đào (hoặc đào đã lâu), nhiều QC/ngày lên trước."""
    dug, mk = db.digs(), db.marks()
    cut = int(time.time()) - config.DIG_FRESH_DAYS * 86400
    return [v for v in db.list_videos()
            if (v["label"] == "sap_win" or v.get("potential")) and "hidden" not in mk.get(v["cid"], ())
            and dug.get(v["cid"], 0) < cut]


# ---- quét store win: soi mọi shop đang chạy video hot để tìm sản phẩm khác của họ ----

TAB_NAMES = {"sap_win": "Sắp WIN", "win": "Video Win", "scale": "Video scale"}


def store_rows():
    """Shop đang chạy video ở các tab Sắp WIN / Win / Scale / Tiềm năng / Bò sữa / Video test / Theo dõi."""
    mk = db.marks()
    followed = {f["key"] for f in db.list_follows() if f["kind"] == "shop"}
    tabs = {}
    for v in db.list_videos():
        m = mk.get(v["cid"], set())
        if "hidden" in m:
            continue
        names = ([TAB_NAMES[v["label"]]] if v["label"] in TAB_NAMES else []) + (["Tiềm năng"] if v.get("potential") else []) \
            + (["Bò sữa"] if v.get("cash_cow") else []) + (["Video test"] if "test" in m else [])
        if not names:
            continue
        for d in v["shops"]:
            t = tabs.setdefault(d, {"tabs": set(), "videos": 0})
            t["tabs"].update(names)
            t["videos"] += 1
    for d in followed:
        tabs.setdefault(d, {"tabs": set(), "videos": 0})["tabs"].add("Theo dõi")
    shops = {r["domain"]: r for r in db.shop_rows()}
    sweeps = db.store_sweeps()
    cut = int(time.time()) - config.STORE_FRESH_DAYS * 86400
    order = ["Theo dõi", "Sắp WIN", "Video Win", "Video scale", "Tiềm năng", "Bò sữa", "Video test"]
    out = []
    for d, t in tabs.items():
        r, sw = shops.get(d, {}), sweeps.get(d, {})
        out.append({"domain": d, "tabs": [n for n in order if n in t["tabs"]], "hot_videos": t["videos"],
                    "ads": r.get("ads", 0), "active": r.get("active") or 0, "pages": r.get("pages", 0),
                    "platform": r.get("platform"), "swept_ts": sw.get("swept_ts"), "ads_found": sw.get("ads_found"),
                    "new_videos": sw.get("new_videos"), "status": "done" if (sw.get("swept_ts") or 0) >= cut else "pending"})
    out.sort(key=lambda r: (r["status"] != "pending", -r["ads"], r["domain"]))
    return out


def sweep_job(domain, country):
    from . import scraper

    def run():
        safety.before_scan("facebook", log, should_stop)
        known = {a["ad_id"] for a in db.all_ads()}          # QC đã có trước lượt soi
        log(f"Soi store {domain}")
        ads = scraper.scan_keyword(domain, country, config.DEFAULT_MAX_ADS, log, should_stop, set_progress)
        ads = [a for a in ads if a.get("domain") == domain]    # chỉ QC dẫn về đúng shop
        db.upsert_ads(ads)
        process_after_scan()
        fresh = {a["ad_id"] for a in ads} - known
        new_videos = sum(1 for v in db.list_videos() if any(a["ad_id"] in fresh for a in v["ads"]))
        db.save_store_sweep(domain, len(ads), new_videos)
        log(f"{domain}: {len(ads)} QC, {new_videos} video mới")
        return len(ads)
    return run


def queue_sweeps(domains, country=None):
    country = country or config.DEFAULT_COUNTRY
    return sum(submit("store", f"Soi store {d}", sweep_job(d, country)) for d in domains)


# ---- tự đào từ khoá: lấy từ tên sản phẩm / nội dung của các video đang hot mà bạn chưa quét ----

_STOP = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "your", "you", "my", "our", "is", "it",
         "this", "that", "new", "best", "get", "now", "buy", "shop", "free", "off", "sale", "just", "every", "from",
         "at", "by", "be", "are", "was", "will", "can", "all", "more", "most", "how", "why", "what", "who", "its"}


def _phrase(words, n):
    words = [w for w in words if w not in _STOP and not w.isdigit() and len(w) > 1]
    return " ".join(words[:n]) if len(words) >= 2 else None


def keyword_suggestions(limit=30):
    known = {w["keyword"].lower() for w in db.list_watch_keywords()}
    known |= {(a.get("keyword") or "").lower() for a in db.all_ads()}
    count, source = {}, {}
    for v in db.list_videos():
        if not (v["label"] in ("sap_win", "win", "scale") or v.get("potential") or v.get("cash_cow")):
            continue
        cands = []
        if v.get("product_key"):
            cands.append((_phrase(v["product_key"].split("-"), 4), "tên sản phẩm"))
        cands.append((_phrase(analyze._WORD_RE.findall((v.get("title") or "").lower()), 3), "nội dung QC"))
        for kw, src in cands:
            if kw and kw not in known:
                count[kw] = count.get(kw, 0) + 1
                source.setdefault(kw, src)
    out = sorted(count, key=lambda k: (-count[k], k))[:limit]
    return [{"keyword": k, "videos": count[k], "source": source[k]} for k in out]


# ---- gợi ý từ khoá từ xu hướng: Google Trends + Pinterest Trends ----

def kwtrend_job(source, geo):
    from . import kwtrends, scraper

    def run():
        if source == "google":
            log(f"Lấy tìm kiếm thịnh hành Google Trends ({geo})")
            with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": landing.UA}) as c:
                r = c.get(config.GOOGLE_TRENDS_RSS.format(geo=geo))
                r.raise_for_status()
                items = kwtrends.parse_google_rss(r.text)
        else:
            log(f"Mở Pinterest Trends ({geo})")
            safety.before_scan("pinterest", log, should_stop)
            items = scraper.scan_pinterest(geo, 300, log, should_stop)
        kwtrends.save(db, source, geo, items)
        log(f"Đọc được {len(items)} từ khoá {kwtrends.SOURCES[source]} ({geo})")
        return len(items)
    return run


def known_keywords():
    """Từ khoá đã quét (QC có từ khoá) hoặc đang tự quét mỗi đêm, chữ thường."""
    return {w["keyword"].lower() for w in db.list_watch_keywords()} | db.ad_keywords()
