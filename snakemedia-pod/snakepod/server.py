import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, jobs

STATIC = Path(__file__).parent / "static"
LABELS = {"sap_win": "Sắp WIN", "win": "Video Win", "scale": "Video scale", "theo_doi": "Chờ thêm dữ liệu",
          "trang_cu": "Trang bán cũ", "cu": "Video già"}



@asynccontextmanager
async def lifespan(_app):
    db.init()
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    jobs.start_worker()
    yield


app = FastAPI(title="SNAKEMEDIA POD", lifespan=lifespan)


class ScanIn(BaseModel):
    keyword: str
    country: str = config.DEFAULT_COUNTRY
    max_ads: int = config.DEFAULT_MAX_ADS
    save: bool = False          # lưu từ khoá để tự quét mỗi đêm


class FollowIn(BaseModel):
    kind: str                   # 'page' hoặc 'shop'
    key: str
    name: str | None = None


class AutoIn(BaseModel):
    enabled: bool
    hour: int


DAY = 86400


@app.get("/api/stats")
def stats():
    counts = db.label_counts()
    return {"labels": [{"key": k, "name": n, "count": counts.get(k, 0)} for k, n in LABELS.items()],
            "total": sum(counts.values()), "scans": db.list_scans(10), "now": int(time.time())}


def _facets(items):
    types, niches = {}, {}
    for v in items:
        if v.get("product_type"):
            types[v["product_type"]] = types.get(v["product_type"], 0) + 1
        for n in v.get("niches") or []:
            niches[n] = niches.get(n, 0) + 1
    order = lambda d: [{"name": k, "count": c} for k, c in sorted(d.items(), key=lambda x: -x[1])]
    return {"product_types": order(types), "niches": order(niches)}


@app.get("/api/videos")
def videos(label: str | None = None, q: str | None = None, product_type: str | None = None,
           niche: str | None = None, pod: bool = False, page_id: str | None = None, shop: str | None = None):
    items = db.list_videos(label)
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
    facets = _facets(items)
    if product_type:
        items = [v for v in items if v.get("product_type") == product_type]
    if niche:
        items = [v for v in items if niche in (v.get("niches") or [])]
    for v in items:
        v.pop("ads", None)
    return {"items": items[:500], "total": len(items), "facets": facets}


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
    return v


@app.post("/api/scan")
def scan(body: ScanIn):
    kw = body.keyword.strip()
    if not kw:
        raise HTTPException(400, "Thiếu từ khoá")
    if body.save:
        db.add_watch_keyword(kw, body.country.upper())
    jobs.submit("keyword", f"Quét '{kw}'", jobs.keyword_job(kw, body.country.upper(), max(10, min(body.max_ads, 2000))))
    return {"ok": True}


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
    db.set_setting("auto", {**jobs.auto_settings(), "enabled": body.enabled, "hour": body.hour})
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
