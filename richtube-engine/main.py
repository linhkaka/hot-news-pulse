# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: FastAPI Server (cổng 8000)
# ============================================================================

import asyncio
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from richtube.config import get_settings
from richtube.engine import Engine
from richtube.models import DiscoverRequest, Job, OutlierRecord, SpyRequest
from richtube.telegram import esc
from richtube.youtube import parse_channel_ref, parse_video_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("richtube.api")

settings = get_settings()
MAX_JOBS = 200


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as http:
        app.state.engine = Engine(settings, http)
        app.state.jobs = {}
        app.state.tasks = set()
        yield
        for task in app.state.tasks:
            task.cancel()


app = FastAPI(title="RICHTUBE Engine", version="1.0.0", lifespan=lifespan)

# Cho phép Web Dashboard (cổng 3000) gọi trực tiếp sang API (cổng 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def engine_of(request: Request) -> Engine:
    return request.app.state.engine


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if settings.richtube_api_key and not (
        x_api_key and secrets.compare_digest(x_api_key, settings.richtube_api_key)
    ):
        raise HTTPException(status_code=401, detail="Sai hoặc thiếu X-API-Key")


def start_job(request: Request, kind: str, input_value: str, work) -> Job:
    jobs: dict[str, Job] = request.app.state.jobs
    job = Job(job_id=uuid.uuid4().hex[:12], kind=kind, input=input_value)
    jobs[job.job_id] = job
    while len(jobs) > MAX_JOBS:
        jobs.pop(next(iter(jobs)))

    async def runner():
        job.status = "running"
        try:
            result = await work()
            records = result if isinstance(result, list) else [result]
            job.result_video_ids = [r.video_id for r in records]
            job.status = "done"
        except Exception as exc:
            log.exception("Job %s thất bại", job.job_id)
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(timezone.utc).isoformat()

    task = asyncio.create_task(runner())
    request.app.state.tasks.add(task)
    task.add_done_callback(request.app.state.tasks.discard)
    return job


@app.get("/health")
async def health(request: Request):
    engine = engine_of(request)
    return {
        "status": "online",
        "gemini_pool_size": engine.gemini.size,
        "youtube_configured": engine.youtube.configured,
        "lark_configured": engine.lark.configured,
        "telegram_configured": engine.telegram.configured,
        "records": len(engine.store),
    }


@app.get("/api/v1/outliers", response_model=list[OutlierRecord])
async def list_outliers(request: Request, market: Optional[str] = None):
    return engine_of(request).store.list(market)


@app.get("/api/v1/outliers/{video_id}", response_model=OutlierRecord)
async def get_outlier(request: Request, video_id: str):
    record = engine_of(request).store.get(video_id)
    if not record:
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu cho video này")
    return record


def ensure_ready(engine: Engine) -> None:
    missing = [name for name, ok in (("YOUTUBE_API_KEY", engine.youtube.configured), ("GEMINI_API_KEYS", engine.gemini.size > 0)) if not ok]
    if missing:
        raise HTTPException(status_code=503, detail=f"Engine chưa cấu hình: {', '.join(missing)}")


@app.post("/api/v1/spy/video", status_code=202, response_model=Job, dependencies=[Depends(require_api_key)])
async def spy_video(request: Request, body: SpyRequest):
    engine = engine_of(request)
    if not parse_video_id(body.video_url):
        raise HTTPException(status_code=422, detail="Link video YouTube không hợp lệ")
    ensure_ready(engine)

    async def work():
        try:
            return await engine.spy(body.video_url, notify=body.notify_telegram, chat_id=body.telegram_chat_id)
        except Exception as exc:
            if body.notify_telegram:
                await engine.telegram.send(f"❌ Spy thất bại: {esc(exc)}", body.telegram_chat_id)
            raise

    return start_job(request, "spy", body.video_url, work)


@app.post("/api/v1/discover/channel", status_code=202, response_model=Job, dependencies=[Depends(require_api_key)])
async def discover_channel(request: Request, body: DiscoverRequest):
    engine = engine_of(request)
    if not parse_channel_ref(body.seed_channel_url):
        raise HTTPException(status_code=422, detail="Link kênh YouTube không hợp lệ")
    ensure_ready(engine)

    async def work():
        try:
            return await engine.discover(
                body.seed_channel_url, body.target_markets, notify=body.notify_telegram, chat_id=body.telegram_chat_id
            )
        except Exception as exc:
            if body.notify_telegram:
                await engine.telegram.send(f"❌ Tìm kênh thất bại: {esc(exc)}", body.telegram_chat_id)
            raise

    return start_job(request, "discover", body.seed_channel_url, work)


@app.get("/api/v1/jobs", response_model=list[Job])
async def list_jobs(request: Request):
    return list(reversed(request.app.state.jobs.values()))


@app.get("/api/v1/jobs/{job_id}", response_model=Job)
async def get_job(request: Request, job_id: str):
    job = request.app.state.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy job")
    return job
