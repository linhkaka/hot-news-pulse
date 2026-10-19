# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Nevlex Core - mổ xẻ cấu trúc video & sinh Blueprint sản xuất bằng Gemini
# ============================================================================

import json
import logging

from pydantic import BaseModel, ValidationError

from .gemini import GeminiError, GeminiPool
from .models import Blueprint, Deconstruction, HeatmapPoint

log = logging.getLogger("richtube.analyzer")


class AnalysisResult(BaseModel):
    spike_notes: list[str] = []
    drop_notes: list[str] = []
    deconstruction: Deconstruction
    blueprint: Blueprint


OUTPUT_SHAPE = {
    "spike_notes": ["<giải thích vì sao khán giả xem lại đoạn đỉnh #1>", "..."],
    "drop_notes": ["<giải thích vì sao khán giả bỏ qua vùng trũng #1>"],
    "deconstruction": {
        "packaging_analysis": {"visual_trigger": "", "curiosity_gap": "", "psychological_angle": ""},
        "hook_30s_breakdown": {"opening_mechanism": "", "pacing_notes": "", "core_loop_opened": ""},
        "narrative_beats": [
            {"time_range": "00:00 - 00:45", "beat_name": "", "retention_technique": "", "structural_purpose": ""}
        ],
        "exploitable_gaps": {
            "unanswered_questions": [""],
            "viewer_complaints_or_debates": "",
            "superior_angle_proposal": "",
        },
    },
    "blueprint": {
        "packaging_blueprint": {
            "titles": ["", "", ""],
            "thumbnail_concepts": [{"layout_description": "", "ai_image_prompt": ""}],
        },
        "production_script": [
            {
                "scene_id": 1,
                "estimated_time": "00:00 - 00:07",
                "beat_function": "",
                "voiceover_script": "",
                "visual_direction": "",
                "visual_generation_prompt": "",
                "audio_sfx_cues": "",
            }
        ],
    },
}


def build_prompt(
    *,
    title: str,
    channel: str,
    description: str,
    market: str,
    stats: str,
    spikes: list[HeatmapPoint],
    drops: list[HeatmapPoint],
    transcript: str,
    comments: list[str],
    title_language: str,
    script_language: str,
    watching_video: bool,
) -> str:
    spike_lines = "\n".join(f"#{i+1} [{p.time_range}] cường độ {p.intensity}" for i, p in enumerate(spikes)) or "(không có dữ liệu)"
    drop_lines = "\n".join(f"#{i+1} [{p.time_range}] cường độ {p.intensity}" for i, p in enumerate(drops)) or "(không có dữ liệu)"
    comment_lines = "\n".join(comments[:60]) or "(không có bình luận)"
    video_note = (
        "Bạn được xem trực tiếp 2 phút đầu video: hãy đếm số lần cắt cảnh, mô tả âm thanh/nhạc và hình ảnh thật trong 30s đầu."
        if watching_video
        else "Bạn không xem được video, hãy suy luận nhịp dựng từ transcript."
    )

    return f"""Bạn là Trưởng phòng Chiến lược Nội dung YouTube của Công ty TNHH SNAKEMEDIA.
Nhiệm vụ: mổ xẻ video outlier dưới đây và viết bản đặc tả sản xuất để đội Biên kịch/Editor làm một video VƯỢT MẶT nó
(góc nhìn mới, lấp các lỗ hổng khán giả phàn nàn, KHÔNG sao chép nội dung).

=== THÔNG TIN VIDEO ===
Tiêu đề: {title}
Kênh: {channel}
Thị trường: {market}
Chỉ số: {stats}
Mô tả: {description[:1500]}

=== MOST REPLAYED HEATMAP ===
Đỉnh giữ chân:
{spike_lines}
Vùng trũng:
{drop_lines}

=== TRANSCRIPT (có timecode) ===
{transcript or "(không có transcript)"}

=== TOP BÌNH LUẬN ===
{comment_lines}

=== YÊU CẦU ===
- {video_note}
- Mọi phân tích viết bằng tiếng Việt, cụ thể, có timecode, không chung chung.
- spike_notes / drop_notes: đúng số lượng và thứ tự như danh sách đỉnh/vùng trũng ở trên (rỗng nếu không có dữ liệu).
- narrative_beats: 4-8 nhịp bao phủ toàn bộ video.
- exploitable_gaps: rút ra từ bình luận thật; superior_angle_proposal là góc triển khai mới đủ mạnh để làm video riêng.
- titles: đúng 3 phương án, viết bằng {title_language}, giữ công thức CTR của video gốc nhưng theo góc mới.
- thumbnail_concepts: 1-2 phương án; ai_image_prompt viết bằng tiếng Anh, sẵn sàng dán vào Midjourney/Whisk (thêm --ar 16:9).
- production_script: 8-12 cảnh bao phủ hook và hồi 1 (khoảng 2-3 phút đầu) của video MỚI;
  voiceover_script viết bằng {script_language} (có chỉ dẫn giọng trong ngoặc vuông);
  visual_generation_prompt viết bằng tiếng Anh; audio_sfx_cues ghi rõ hiệu ứng và thời điểm.

Chỉ trả về MỘT object JSON đúng cấu trúc sau (thay nội dung mẫu bằng nội dung thật):
{json.dumps(OUTPUT_SHAPE, ensure_ascii=False, indent=1)}
"""


async def analyze(gemini: GeminiPool, prompt: str, video_url: str | None) -> AnalysisResult:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = await gemini.generate_json(prompt, video_url=video_url)
            return AnalysisResult.model_validate(raw)
        except ValidationError as exc:
            log.warning("Gemini trả JSON sai cấu trúc (lần %s): %s", attempt + 1, exc)
            last_error = exc
            prompt += f"\n\nLẦN TRƯỚC BẠN TRẢ SAI CẤU TRÚC. Lỗi: {str(exc)[:800]}\nHãy trả lại JSON đúng cấu trúc."
    raise GeminiError(f"Gemini trả JSON sai cấu trúc 2 lần liên tiếp: {last_error}")
