# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Pydantic models (khớp 100% với richtube-web/src/types/richtube.ts)
# ============================================================================

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

MARKETS = ["US", "JP", "KR", "ES", "DE", "FR"]


class HeatmapPoint(BaseModel):
    time_range: str
    intensity: float = Field(ge=0, le=1)
    note: str = ""


class HeatmapPeaks(BaseModel):
    retention_spikes: list[HeatmapPoint] = []
    retention_drops: list[HeatmapPoint] = []


class NarrativeBeat(BaseModel):
    time_range: str
    beat_name: str
    retention_technique: str
    structural_purpose: str


class PackagingAnalysis(BaseModel):
    visual_trigger: str
    curiosity_gap: str
    psychological_angle: str


class Hook30sBreakdown(BaseModel):
    opening_mechanism: str
    pacing_notes: str
    core_loop_opened: str


class ExploitableGaps(BaseModel):
    unanswered_questions: list[str]
    viewer_complaints_or_debates: str
    superior_angle_proposal: str


class Deconstruction(BaseModel):
    packaging_analysis: PackagingAnalysis
    hook_30s_breakdown: Hook30sBreakdown
    narrative_beats: list[NarrativeBeat]
    exploitable_gaps: ExploitableGaps


class ThumbnailConcept(BaseModel):
    layout_description: str
    ai_image_prompt: str


class PackagingBlueprint(BaseModel):
    titles: list[str]
    thumbnail_concepts: list[ThumbnailConcept]


class ProductionScene(BaseModel):
    scene_id: int
    estimated_time: str
    beat_function: str
    voiceover_script: str
    visual_direction: str
    visual_generation_prompt: str
    audio_sfx_cues: str


class Blueprint(BaseModel):
    packaging_blueprint: PackagingBlueprint
    production_script: list[ProductionScene]


class OutlierRecord(BaseModel):
    video_id: str
    title: str
    channel_name: str
    market: str
    url: str
    thumbnail_url: str
    tae_score: float
    current_vph: int
    baseline_vph: int
    published_hours_ago: int
    lark_synced: bool = False
    lark_record_id: Optional[str] = None
    analyzed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: int = 0
    # Đường cong Most Replayed của cả video (~100 điểm, 0..1, cách đều nhau)
    heatmap_curve: list[float] = []

    heatmap_peaks: HeatmapPeaks
    deconstruction: Deconstruction
    blueprint: Blueprint


# ---------- Request / Job ----------

class SpyRequest(BaseModel):
    video_url: str
    notify_telegram: bool = True
    telegram_chat_id: Optional[str] = None


class DiscoverRequest(BaseModel):
    seed_channel_url: str
    target_markets: list[str] = Field(default_factory=lambda: list(MARKETS))
    notify_telegram: bool = True
    telegram_chat_id: Optional[str] = None


class WatchRequest(BaseModel):
    channel_url: str


class WatchChannel(BaseModel):
    channel_id: str
    title: str
    market: str
    thumbnail_url: str = ""
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_scanned_at: Optional[str] = None


class Job(BaseModel):
    job_id: str
    kind: Literal["spy", "discover", "radar"]
    status: Literal["queued", "running", "done", "failed"] = "queued"
    input: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None
    error: Optional[str] = None
    result_video_ids: list[str] = []
