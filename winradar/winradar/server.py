import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, jobs

STATIC = Path(__file__).parent / "static"
LABELS = {"sap_win": "Sắp WIN", "win": "Video Win", "scale": "Video scale", "theo_doi": "Theo dõi",
          "trang_cu": "Trang bán cũ", "cu": "Video già"}



@asynccontextmanager
async def lifespan(_app):
    db.init()
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    jobs.start_worker()
    yield


app = FastAPI(title="WinRadar", lifespan=lifespan)


class ScanIn(BaseModel):
    keyword: str
    country: str = config.DEFAULT_COUNTRY
    max_ads: int = config.DEFAULT_MAX_ADS


@app.get("/api/stats")
def stats():
    counts = db.label_counts()
    return {"labels": [{"key": k, "name": n, "count": counts.get(k, 0)} for k, n in LABELS.items()],
            "total": sum(counts.values()), "scans": db.list_scans(10), "now": int(time.time())}


@app.get("/api/videos")
def videos(label: str | None = None, q: str | None = None):
    items = db.list_videos(label)
    if q:
        ql = q.lower()
        items = [v for v in items if ql in (v["title"] or "").lower() or any(ql in s for s in v["shops"])
                 or any(ql in k.lower() for k in v["keywords"])]
    for v in items:
        v.pop("ads", None)
    return {"items": items[:500], "total": len(items)}


@app.get("/api/videos/{cid}")
def video(cid: str):
    v = db.get_video(cid)
    if not v:
        raise HTTPException(404)
    return v


@app.post("/api/scan")
def scan(body: ScanIn):
    kw = body.keyword.strip()
    if not kw:
        raise HTTPException(400, "Thiếu từ khoá")
    jobs.submit("keyword", f"Quét '{kw}'", jobs.keyword_job(kw, body.country.upper(), max(10, min(body.max_ads, 2000))))
    return {"ok": True}


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
