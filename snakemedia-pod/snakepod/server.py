import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import threading

from . import config, db, diag, jobs, media, notify, safety, social

STATIC = Path(__file__).parent / "static"
LABELS = {"sap_win": "Sắp WIN", "win": "Video Win", "scale": "Video scale", "theo_doi": "Chờ thêm dữ liệu",
          "trang_cu": "Trang bán cũ", "cu": "Video già"}



@asynccontextmanager
async def lifespan(_app):
    db.init()
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    jobs.start_worker()
    # Cập nhật lên bản có tab Tiềm năng / Bò sữa / lịch sử: chấm lại 1 lần để video cũ có đủ số liệu mới
    if db.get_setting("schema", 1) < 2:
        db.set_setting("schema", 2)
        if db.list_videos():
            jobs.submit("recompute", "Chấm lại (bản nâng cấp)", lambda: jobs.recompute() or 0)
    yield


app = FastAPI(title="SNAKEMEDIA POD", lifespan=lifespan)


class ScanIn(BaseModel):
    keyword: str = ""
    keywords: list[str] = []    # quét hàng loạt: mỗi dòng 1 từ khoá
    country: str = config.DEFAULT_COUNTRY
    max_ads: int = config.DEFAULT_MAX_ADS
    save: bool = False          # lưu từ khoá để tự quét mỗi đêm


class FollowIn(BaseModel):
    kind: str                   # 'page' hoặc 'shop'
    key: str
    name: str | None = None


class SocialScanIn(BaseModel):
    platform: str               # tiktok | tiktok_ads | tiktok_trend | tiktok_tags | fb_reels
    keyword: str = ""
    keywords: list[str] = []    # nhiều từ khoá / #hashtag
    country: str = config.DEFAULT_COUNTRY
    countries: list[str] = []   # nhiều thị trường (chỉ nguồn Creative Center dùng)
    max_items: int = 200
    period: int = 7             # Top Ads: 7 / 30 / 180 ngày
    save: bool = False


class LimitsIn(BaseModel):
    platform: str
    min_gap_s: int
    max_per_day: int


class NotifyIn(BaseModel):
    telegram_token: str | None = None      # bỏ trống = giữ token cũ; "" = xoá
    telegram_chat_id: str | None = None
    windows: bool | None = None
    desktop: bool | None = None            # tên dùng chung với bản tiện ích Chrome (= windows)
    events: dict | None = None


class AutoIn(BaseModel):
    enabled: bool
    hour: int
    stores: int | None = None   # số shop soi thêm mỗi đêm


class MediaBatchIn(BaseModel):
    cids: list[str] = []        # video QC Facebook
    vids: list[str] = []        # video viral
    kind: str = "video"         # video | image | both


class MarkIn(BaseModel):
    cid: str
    kind: str                   # 'test' | 'hidden'
    on: bool = True


class CountIn(BaseModel):
    n: int = 10
    domains: list[str] = []


DAY = 86400


@app.get("/api/stats")
def stats():
    counts = db.label_counts()
    vids, mk = db.list_videos(), db.marks()
    shown = [v for v in vids if "hidden" not in mk.get(v["cid"], ())]
    tabs = {"potential": sum(1 for v in shown if v.get("potential")), "cow": sum(1 for v in shown if v.get("cash_cow")),
            "test": sum(1 for m in mk.values() if "test" in m), "hidden": sum(1 for m in mk.values() if "hidden" in m),
            "dig": len(jobs.dig_candidates()), "stores": sum(1 for r in jobs.store_rows() if r["status"] == "pending")}
    return {"labels": [{"key": k, "name": n, "count": counts.get(k, 0)} for k, n in LABELS.items()],
            "total": sum(counts.values()), "tabs": tabs, "scans": db.list_scans(10), "now": int(time.time())}


def _facets(items):
    types, niches = {}, {}
    for v in items:
        if v.get("product_type"):
            types[v["product_type"]] = types.get(v["product_type"], 0) + 1
        for n in v.get("niches") or []:
            niches[n] = niches.get(n, 0) + 1
    order = lambda d: [{"name": k, "count": c} for k, c in sorted(d.items(), key=lambda x: -x[1])]
    return {"product_types": order(types), "niches": order(niches)}


TAB_SORTS = {"potential": lambda v: (v.get("ads_new_48h", 0), v["ads_per_day"]),
             "cow": lambda v: (v["buckets"]["old"], v["ads_per_day"])}


def _decorate(items):
    """Gắn đánh dấu (Video test / Đã ẩn), lần đào gần nhất và thay đổi so với hôm trước (lịch sử theo dõi)."""
    mk, dug = db.marks(), db.digs()
    hist = db.history([v["cid"] for v in items], 2)
    for v in items:
        v["marks"] = sorted(mk.get(v["cid"], ()))
        v["dug_ts"] = dug.get(v["cid"])
        h = hist.get(v["cid"]) or []
        v["delta"] = ({k: h[0][k] - h[1][k] for k in ("pages_active", "shops_active", "shops_win", "scale", "urls")}
                      if len(h) >= 2 else None)
    return items


@app.get("/api/videos")
def videos(label: str | None = None, q: str | None = None, product_type: str | None = None,
           niche: str | None = None, pod: bool = False, page_id: str | None = None, shop: str | None = None,
           spread: bool = False, product: str | None = None, tab: str | None = None, offset: int = 0, limit: int = 60):
    items = db.list_videos(label)
    mk = db.marks()
    if tab == "hidden":
        items = [v for v in items if "hidden" in mk.get(v["cid"], ())]
    else:
        items = [v for v in items if "hidden" not in mk.get(v["cid"], ())]
    if tab == "test":
        items = [v for v in items if "test" in mk.get(v["cid"], ())]
    elif tab == "potential":
        items = [v for v in items if v.get("potential")]
    elif tab == "cow":
        items = [v for v in items if v.get("cash_cow")]
    elif tab == "dig":
        items = jobs.dig_candidates()
    if tab in TAB_SORTS:
        items = sorted(items, key=TAB_SORTS[tab], reverse=True)
    if spread:   # QC Facebook đang lan nhanh: xếp theo số QC mới 48h
        items = sorted((v for v in items if v.get("spreading")),
                       key=lambda v: (v.get("ads_new_48h", 0), v.get("shops_new_48h", 0)), reverse=True)
    if q:
        ql = q.lower()
        items = [v for v in items if ql in (v["title"] or "").lower() or any(ql in s for s in v["shops"])
                 or any(ql in k.lower() for k in v["keywords"])]
    if pod:
        items = [v for v in items if v.get("is_pod")]
    if page_id:
        items = [v for v in items if page_id in v["page_ids"]]
    if shop:
        items = [v for v in items if shop in v["shops"]]
    if product:
        items = [v for v in items if v.get("product_key") == product]
    facets = _facets(items)
    if product_type:
        items = [v for v in items if v.get("product_type") == product_type]
    if niche:
        items = [v for v in items if niche in (v.get("niches") or [])]
    page = _page(items, offset, limit)
    for v in page:
        v.pop("ads", None)
    return {"items": _decorate(page), "total": len(items), "offset": max(0, offset), "facets": facets}


def _page(items, offset, limit):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return items[offset:offset + limit]


# ---- video viral: TikTok / TikTok Top Ads / Facebook Reels ----

def _social_list(platform=None):
    rows = db.social_rows(platform)
    snaps = db.social_snapshots({r["vid"] for r in rows})
    return [social.summarize(r, snaps.get(r["vid"], [])) for r in rows]


SOCIAL_SORTS = {"vph": lambda v: v["sort_vph"], "views": lambda v: v.get("views") or 0,
                "likes": lambda v: v.get("likes") or 0, "engagement": lambda v: v.get("engagement") or 0,
                "new": lambda v: v.get("created_ts") or v.get("first_seen") or 0}


@app.get("/api/viral")
def viral(platform: str | None = None, label: str | None = None, q: str | None = None,
          product_type: str | None = None, niche: str | None = None, pod: bool = False, sort: str = "vph",
          market: str | None = None, offset: int = 0, limit: int = 60):
    items = _social_list(platform)
    markets = {}
    for v in items:
        if v.get("market"):
            markets[v["market"]] = markets.get(v["market"], 0) + 1
    if market:
        items = [v for v in items if v.get("market") == market]
    counts = {k: 0 for k in social.LABELS}
    for v in items:
        counts[v["label"]] += 1
    if label:
        items = [v for v in items if v["label"] == label]
    if q:
        ql = q.lower()
        items = [v for v in items if ql in (v.get("caption") or "").lower() or ql in (v.get("author") or "").lower()
                 or ql in (v.get("keyword") or "").lower()]
    if pod:
        items = [v for v in items if v["is_pod"]]
    facets = _facets(items)
    if product_type:
        items = [v for v in items if v["product_type"] == product_type]
    if niche:
        items = [v for v in items if niche in v["niches"]]
    items.sort(key=SOCIAL_SORTS.get(sort, SOCIAL_SORTS["vph"]), reverse=True)
    page = _page(items, offset, limit)
    for v in page:
        v.pop("snapshots", None)
    return {"items": page, "total": len(items), "offset": max(0, offset), "facets": facets, "counts": counts,
            "labels": social.LABELS, "platforms": social.PLATFORMS, "markets": markets}


@app.get("/api/viral/keywords")
def viral_keywords():
    return db.list_social_watch()


@app.delete("/api/viral/keywords/{platform}/{keyword}")
def delete_viral_keyword(platform: str, keyword: str, country: str | None = None):
    db.remove_social_watch(platform, keyword.strip(), country)   # Top Ads không từ khoá được gửi là " "
    return {"ok": True}


@app.get("/api/markets")
def markets():
    return {"markets": config.MARKETS, "sources": social.SOURCES, "market_sources": sorted(social.MARKET_SOURCES)}


@app.post("/api/viral/scan")
def viral_scan(body: SocialScanIn):
    if body.platform not in social.SOURCES:
        raise HTTPException(400, "Nền tảng không hợp lệ")
    kws = list(dict.fromkeys(k.strip() for k in [body.keyword, *body.keywords] if k and k.strip()))
    by_market = body.platform in social.MARKET_SOURCES
    if not kws:
        if not by_market:
            raise HTTPException(400, "Thiếu từ khoá")
        kws = [""]
    countries = list(dict.fromkeys(c.strip().upper() for c in [*body.countries] if c.strip())) or [body.country.upper()]
    if not by_market:
        countries = [countries[0]]        # TikTok tìm kiếm / Reels: thị trường theo tài khoản + IP, quét 1 lần
    max_items = max(10, min(body.max_items, 1000))
    queued = 0
    for kw in kws[:50]:
        for country in countries[:20]:
            if body.save:
                db.add_social_watch(body.platform, kw, country if by_market else "")
            queued += jobs.submit("social", jobs.social_title(body.platform, kw, country),
                                  jobs.social_job(body.platform, kw, country, max_items, body.period))
    return {"ok": True, "queued": queued}


@app.get("/api/trends")
def trends(market: str | None = None, q: str | None = None):
    """Hashtag xu hướng theo thị trường; đánh dấu hashtag khớp từ khoá bạn đang theo dõi."""
    rows = db.list_trends()
    present = sorted({r["market"] for r in rows})
    words = {w["keyword"].lower().lstrip("#") for w in db.list_social_watch() if w["keyword"]}
    words |= {w["keyword"].lower() for w in db.list_watch_keywords()}
    tokens = {t for w in words for t in w.replace("#", " ").split() if len(t) > 2}
    if market:
        rows = [r for r in rows if r["market"] == market]
    if q:
        ql = q.lower().lstrip("#")
        rows = [r for r in rows if ql in r["name"]]
    for r in rows:
        r["match"] = sorted(t for t in tokens if t in r["name"])
        r["move"] = (r["prev_rank"] - r["rank"]) if r["prev_rank"] and r["rank"] else None
    return {"items": rows, "markets": present, "names": config.MARKETS}


# ---- tải ảnh / video ----

def _media_urls(kind, key):
    """[(link, tên gợi ý, link ảnh lưu sẵn trong máy)] của 1 QC / 1 video QC / 1 video viral."""
    if kind == "ad":
        a = next((a for a in db.ads_by_ids([key])), None)
        if not a:
            raise HTTPException(404)
        return a.get("video_url"), a.get("thumb_url"), a.get("thumb_path"), f"qc-{key}-{media.slug(a.get('body') or a.get('title'))}"
    if kind == "video":
        v = db.get_video(key)
        if not v:
            raise HTTPException(404)
        return v.get("video_url"), v.get("thumb_url"), v.get("thumb"), f"{v['label']}-{media.slug(v['title'])}-{key}"
    r = db.social_row(key)
    if not r:
        raise HTTPException(404)
    return r.get("video_url"), r.get("cover_url"), r.get("cover_path"), f"{r['platform']}-{media.slug(r.get('caption'))}-{r['item_id']}"


def _media_bytes(video_url, image_url, local, kind):
    """Tải file; ảnh hỏng link thì dùng bản đã lưu trong máy."""
    url = video_url if kind == "video" else image_url
    try:
        if not url:
            raise ValueError("QC này không có video" if kind == "video" else "Không có ảnh")
        data, ctype = media.fetch(url)
        return data, media.ext_for(ctype, url, kind), ctype or "application/octet-stream"
    except Exception as e:
        path = config.THUMB_DIR / local if (kind == "image" and local) else None
        if path and path.exists():
            return path.read_bytes(), ".jpg", "image/jpeg"
        raise HTTPException(502, str(e)[:300])


@app.get("/api/media/{kind}/{key:path}")
def media_download(kind: str, key: str, type: str = "video"):
    """Tải 1 file về máy (trình duyệt hỏi nơi lưu). kind: ad | video | social; type: video | image."""
    if kind not in ("ad", "video", "social") or type not in ("video", "image"):
        raise HTTPException(404)
    video_url, image_url, local, name = _media_urls(kind, key)
    data, ext, ctype = _media_bytes(video_url, image_url, local, type)
    return Response(data, media_type=ctype, headers={"Content-Disposition": f'attachment; filename="{name}{ext}"'})


@app.post("/api/media/batch")
def media_batch(body: MediaBatchIn):
    if body.kind not in ("video", "image", "both"):
        raise HTTPException(400, "kind phải là video / image / both")
    targets = [("video", c) for c in body.cids] + [("social", v) for v in body.vids]
    if not targets:
        raise HTTPException(400, "Chưa chọn video nào")
    targets = targets[:config.MEDIA_BATCH_MAX]

    def run():
        kinds = ["video", "image"] if body.kind == "both" else [body.kind]
        ok = fail = 0
        folder = None
        for kind, key in targets:
            if jobs.should_stop():
                break
            try:
                urls = _media_urls(kind, key)
            except HTTPException:
                continue
            for t in kinds:
                try:
                    data, ext, _ = _media_bytes(*urls[:3], t)
                    folder = media.save(data, urls[3] + ext).parent
                    ok += 1
                except HTTPException as e:
                    fail += 1
                    jobs.log(f"  bỏ qua {urls[3]} ({t}): {e.detail}")
        jobs.log(f"Đã lưu {ok} file" + (f" vào {folder}" if folder else "") + (f", {fail} file lỗi" if fail else ""))
        return ok
    queued = jobs.submit("media", f"Tải {len(targets)} video ({body.kind})", run)
    return {"queued": int(queued), "folder": str(config.MEDIA_DIR)}


@app.get("/api/viral/{vid:path}")
def viral_detail(vid: str):
    r = db.social_row(vid)
    if not r:
        raise HTTPException(404)
    return social.summarize(r, db.social_snapshots({vid}).get(vid, []))


# ---- chế độ an toàn ----

SAFETY_TIPS = [
    "Dùng 1 tài khoản Facebook/TikTok phụ đã dùng bình thường một thời gian, đừng dùng tài khoản mới tạo.",
    "Không quét khi đang bật VPN đổi quốc gia liên tục. Nếu dùng proxy, dùng 1 proxy dân cư cố định.",
    "Giữ trình duyệt của tool hiện lên (không chạy ẩn) — nền tảng ít nghi ngờ hơn.",
    "Gặp checkpoint: tự xác minh trên cửa sổ trình duyệt của tool, đợi vài tiếng rồi mới quét tiếp.",
    "Đừng tăng giới hạn quét/ngày quá cao; quét đều mỗi đêm an toàn hơn quét dồn một lúc.",
]


@app.get("/api/safety")
def safety_status():
    return {"platforms": safety.status(), "tips": SAFETY_TIPS}


@app.post("/api/safety/resume/{platform}")
def safety_resume(platform: str):
    if platform not in safety.PLATFORMS:
        raise HTTPException(404)
    safety.resume(platform)
    jobs.log(f"Đã mở lại quét {safety.PLATFORMS[platform]}")
    return {"ok": True}


@app.post("/api/safety/limits")
def safety_limits(body: LimitsIn):
    try:
        safety.set_limits(body.platform, body.min_gap_s, body.max_per_day)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# ---- thông báo Telegram / Windows ----

@app.get("/api/notify")
def notify_get():
    return notify.public_settings()


@app.post("/api/notify")
def notify_save(body: NotifyIn):
    windows = body.windows if body.windows is not None else body.desktop
    notify.save_settings(body.telegram_token, body.telegram_chat_id, windows, body.events)
    return notify.public_settings()


@app.post("/api/notify/find-chat")
def notify_find_chat():
    s = notify.settings()
    if not s["telegram_token"]:
        raise HTTPException(400, "Chưa nhập token bot Telegram")
    try:
        chat = notify.find_chat_id(s["telegram_token"])
    except Exception as e:
        raise HTTPException(400, f"Không đọc được tin nhắn của bot: {e}")
    if not chat:
        raise HTTPException(400, "Chưa thấy tin nhắn nào. Mở Telegram, nhắn /start cho bot của bạn rồi bấm lại.")
    notify.save_settings(telegram_chat_id=chat)
    return notify.public_settings()


@app.post("/api/notify/test")
def notify_test():
    msgs = []
    sent = notify.send("🐍 SNAKEMEDIA POD: thử thông báo", ["Nếu bạn thấy tin này, thông báo đã chạy."], msgs.append)
    if not sent:
        raise HTTPException(400, "; ".join(msgs) or "Chưa bật kênh nào (nhập Telegram hoặc bật thông báo Windows)")
    return {"sent": sent, "errors": msgs}


@app.get("/api/diag")
def diag_list():
    return diag.list_bundles()


@app.get("/api/diag/{name}/download")
def diag_download(name: str):
    data = diag.zip_bundle(name)
    if data is None:
        raise HTTPException(404)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


@app.post("/api/login/{site}")
def open_login(site: str):
    """Mở cửa sổ trình duyệt của tool để bạn tự đăng nhập / xác minh checkpoint."""
    from . import login
    if site not in login.SITES:
        raise HTTPException(404)
    if jobs.status()["current"]:
        raise HTTPException(409, "Đang có lượt quét chạy, bấm Dừng rồi thử lại")
    threading.Thread(target=login.main, args=(site,), daemon=True).start()
    return {"ok": True}


@app.get("/api/niches")
def niches(pod: bool = True):
    """Bảng niche: niche nào đang có nhiều video Sắp WIN / Win / Scale."""
    rows = {}
    for v in db.list_videos():
        if pod and not v.get("is_pod"):
            continue
        for n in v.get("niches") or ["(chưa rõ niche)"]:
            r = rows.setdefault(n, {"niche": n, "sap_win": 0, "win": 0, "scale": 0, "total": 0, "ads_per_day": 0.0,
                                    "types": {}, "top": None})
            r["total"] += 1
            if v["label"] in ("sap_win", "win", "scale"):
                r[v["label"]] += 1
            r["ads_per_day"] += v["ads_per_day"]
            if v.get("product_type"):
                r["types"][v["product_type"]] = r["types"].get(v["product_type"], 0) + 1
            if v["label"] in ("sap_win", "win") and (not r["top"] or v["ads_per_day"] > r["top"]["ads_per_day"]):
                r["top"] = {"cid": v["cid"], "title": v["title"], "ads_per_day": v["ads_per_day"]}
    out = sorted(rows.values(), key=lambda r: (r["sap_win"] + r["win"], r["scale"], r["ads_per_day"]), reverse=True)
    for r in out:
        r["ads_per_day"] = round(r["ads_per_day"], 2)
        r["types"] = sorted(r["types"], key=lambda t: -r["types"][t])[:3]
    return out


@app.get("/api/videos/{cid}")
def video(cid: str):
    v = db.get_video(cid)
    if not v:
        raise HTTPException(404)
    followed = {(f["kind"], f["key"]) for f in db.list_follows()}
    names = {}
    for a in v["ads"]:
        names.setdefault(a["page_id"], a.get("page_name") or a["page_id"])
    v["page_list"] = [{"id": p, "name": names.get(p, p), "followed": ("page", p) in followed} for p in v["page_ids"]]
    v["shop_list"] = [{"domain": d, "followed": ("shop", d) in followed} for d in v["shops"]]
    _decorate([v])
    v["media"] = {"video_url": v.get("video_url"), "image_url": v.get("thumb_url"),
                  "video_expires_ts": media.link_expiry(v.get("video_url")), "video_expired": media.expired(v.get("video_url")),
                  "variants": len({a["video_url"] for a in v["ads"] if a.get("video_url")})}
    v["history"] = db.history([cid], config.HISTORY_DAYS)[cid]
    v["sourcing"] = sourcing_links(v)
    return v


def sourcing_links(v):
    """Link tìm nguồn hàng (config.SOURCING): theo tên sản phẩm và theo ảnh."""
    from urllib.parse import quote_plus
    words = (v.get("product_key") or "").replace("-", " ") or " ".join((v.get("title") or "").split()[:8])
    q, image = quote_plus(words), quote_plus(v.get("thumb_url") or "")
    return [{"name": n, "url": t.format(q=q, image=image)} for n, t in config.SOURCING
            if q and ("{image}" not in t or image)]


@app.post("/api/scan")
def scan(body: ScanIn):
    kws = list(dict.fromkeys(k.strip() for k in [body.keyword, *body.keywords] if k and k.strip()))
    if not kws:
        raise HTTPException(400, "Thiếu từ khoá")
    country, max_ads = body.country.upper(), max(10, min(body.max_ads, 2000))
    queued = 0
    for kw in kws[:200]:
        if body.save:
            db.add_watch_keyword(kw, country)
        queued += jobs.submit("keyword", f"Quét '{kw}'", jobs.keyword_job(kw, country, max_ads))
    return {"ok": True, "queued": queued}


@app.get("/api/keywords/suggest")
def keyword_suggest():
    return jobs.keyword_suggestions()


@app.post("/api/marks")
def set_mark(body: MarkIn):
    if body.kind not in ("test", "hidden"):
        raise HTTPException(400, "kind phải là 'test' hoặc 'hidden'")
    db.set_mark(body.cid, body.kind, body.on)
    return {"ok": True}


@app.post("/api/dig/batch")
def dig_batch(body: CountIn):
    n = 0
    for v in jobs.dig_candidates()[:max(1, min(body.n, 50))]:
        n += jobs.submit("dig", f"Đào sâu '{v['title'][:40]}'", jobs.dig_job(v["cid"], config.DEFAULT_COUNTRY))
    return {"queued": n}


@app.get("/api/stores")
def stores(status: str = "pending", offset: int = 0, limit: int = 50):
    rows = jobs.store_rows()
    cut = int(time.time()) - config.STORE_FRESH_DAYS * DAY
    summary = {"total": len(rows), "pending": sum(1 for r in rows if r["status"] == "pending"),
               "done": sum(1 for r in rows if r["status"] == "done"),
               "new_videos_7d": sum(r["new_videos"] or 0 for r in rows if (r["swept_ts"] or 0) >= cut),
               "auto": jobs.auto_settings()}
    if status in ("pending", "done"):
        rows = [r for r in rows if r["status"] == status]
    return {"items": _page(rows, offset, limit), "total": len(rows), "offset": max(0, offset), "summary": summary}


@app.post("/api/stores/sweep")
def stores_sweep(body: CountIn):
    domains = body.domains or [r["domain"] for r in jobs.store_rows() if r["status"] == "pending"][:max(1, min(body.n, 100))]
    return {"queued": jobs.queue_sweeps(domains)}


@app.get("/api/export")
def export_data():
    return db.export_data()


@app.post("/api/import")
def import_data(body: dict):
    try:
        ads, lands = db.import_data(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    jobs.submit("recompute", "Gộp kho + chấm lại", lambda: (jobs.process_after_scan() or 0))
    return {"ads": ads, "landings": lands}


@app.get("/api/info")
def info():
    with db.connect() as conn:
        has = conn.execute("SELECT (SELECT COUNT(*) FROM ads) + (SELECT COUNT(*) FROM social_videos)").fetchone()[0]
    return {"app": True, "demo": False, "has_data": bool(has)}


# ---- từ khoá tự quét + lịch ----

@app.get("/api/keywords")
def keywords():
    return db.list_watch_keywords()


@app.delete("/api/keywords/{keyword}")
def delete_keyword(keyword: str):
    db.remove_watch_keyword(keyword)
    return {"ok": True}


@app.get("/api/autoscan")
def get_autoscan():
    return {**jobs.auto_settings(), "keywords": len(db.list_watch_keywords()), "follows": len(db.list_follows())}


@app.post("/api/autoscan")
def set_autoscan(body: AutoIn):
    if not 0 <= body.hour <= 23:
        raise HTTPException(400, "Giờ phải từ 0 đến 23")
    if body.stores is not None and not 0 <= body.stores <= 200:
        raise HTTPException(400, "Số shop soi mỗi đêm: 0–200")
    cur = jobs.auto_settings()
    db.set_setting("auto", {**cur, "enabled": body.enabled, "hour": body.hour,
                            "stores": cur["stores"] if body.stores is None else body.stores})
    return get_autoscan()


@app.post("/api/autoscan/run")
def run_autoscan():
    return {"queued": jobs.queue_all_watched("Quét tất cả (bấm tay)")}


# ---- theo dõi page / shop + kho shop ----

def _activity(ads, now):
    active = [a for a in ads if a.get("is_active")]
    return {
        "ads": len(ads),
        "active": len(active),
        "new_24h": sum(1 for a in ads if a.get("start_ts") and now - a["start_ts"] <= DAY),
        "new_7d": sum(1 for a in ads if a.get("start_ts") and now - a["start_ts"] <= 7 * DAY),
        "off_2d": sum(1 for a in ads if not a.get("is_active") and a.get("end_ts") and now - a["end_ts"] <= 2 * DAY),
        "first_ts": min((a["start_ts"] for a in ads if a.get("start_ts")), default=None),
    }


@app.get("/api/follows")
def follows():
    now = int(time.time())
    out = []
    for f in db.list_follows():
        ads = db.ads_where("page_id" if f["kind"] == "page" else "domain", f["key"])
        out.append({**f, **_activity(ads, now)})
    return out


@app.post("/api/follows")
def add_follow(body: FollowIn):
    if body.kind not in ("page", "shop") or not body.key.strip():
        raise HTTPException(400, "kind phải là 'page' hoặc 'shop'")
    db.add_follow(body.kind, body.key.strip(), body.name)
    return {"ok": True}


@app.delete("/api/follows/{kind}/{key}")
def delete_follow(kind: str, key: str):
    db.remove_follow(kind, key)
    return {"ok": True}


@app.post("/api/follows/{kind}/{key}/scan")
def scan_follow(kind: str, key: str, country: str = config.DEFAULT_COUNTRY):
    f = next((f for f in db.list_follows() if f["kind"] == kind and f["key"] == key), None)
    if not f:
        raise HTTPException(404)
    jobs.submit("follow", f"Theo dõi {kind} {f['name'] or key}", jobs.follow_job(kind, key, country))
    return {"ok": True}


@app.get("/api/shops")
def shops():
    followed = {f["key"] for f in db.list_follows() if f["kind"] == "shop"}
    vids = db.list_videos()
    out = []
    for r in db.shop_rows():
        mine = [v for v in vids if r["domain"] in v["shops"]]
        out.append({**r, "followed": r["domain"] in followed, "videos": len(mine),
                    "hot": sum(1 for v in mine if v["label"] in ("sap_win", "win")),
                    "pod": any(v.get("is_pod") for v in mine)})
    return out


@app.post("/api/videos/{cid}/dig")
def dig(cid: str, country: str = config.DEFAULT_COUNTRY):
    v = db.get_video(cid)
    if not v:
        raise HTTPException(404)
    jobs.submit("dig", f"Đào sâu '{v['title'][:40]}'", jobs.dig_job(cid, country))
    return {"ok": True}


@app.post("/api/recompute")
def recompute():
    jobs.submit("recompute", "Chấm lại", lambda: jobs.recompute() or 0)
    return {"ok": True}


@app.post("/api/stop")
def stop():
    jobs.stop_current()
    return {"ok": True}


@app.get("/api/jobs")
def job_status():
    return jobs.status()


@app.get("/api/scans")
def scans():
    return db.list_scans()


@app.get("/thumbs/{name}")
def thumb(name: str):
    path = (config.THUMB_DIR / name).resolve()
    if path.parent != config.THUMB_DIR.resolve() or not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
