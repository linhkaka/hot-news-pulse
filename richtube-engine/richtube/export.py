# ============================================================================
# RICHTUBE - YouTube Intelligence & Autonomous Production Engine
# Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
# Module: Xuất kịch bản cho đội Biên kịch / Editor (.md, .csv)
# ============================================================================

import csv
import io

from .models import OutlierRecord


def to_markdown(record: OutlierRecord) -> str:
    d = record.deconstruction
    b = record.blueprint
    lines = [
        f"# {record.title}",
        "",
        f"- Kênh: {record.channel_name} [{record.market}]",
        f"- Link gốc: {record.url}",
        f"- TAE: {record.tae_score}x · {record.current_vph:,} VPH (baseline {record.baseline_vph:,})",
        "",
        "## Góc khai thác vượt mặt đối thủ",
        d.exploitable_gaps.superior_angle_proposal,
        "",
        "**Câu hỏi khán giả chưa được giải đáp:**",
        *[f"- {q}" for q in d.exploitable_gaps.unanswered_questions],
        "",
        "## Tiêu đề đề xuất",
        *[f"{i + 1}. {t}" for i, t in enumerate(b.packaging_blueprint.titles)],
        "",
        "## Thumbnail",
    ]
    for tc in b.packaging_blueprint.thumbnail_concepts:
        lines += [f"- Bố cục: {tc.layout_description}", f"- Prompt: `{tc.ai_image_prompt}`", ""]
    lines += [
        "## Kịch bản phân cảnh 4 cột",
        "",
        "| # | Timecode | Lời thoại (Voiceover) | Chỉ dẫn dựng hình | Visual AI Prompt | Audio / SFX |",
        "|---|---|---|---|---|---|",
    ]

    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", "<br>")

    for s in b.production_script:
        lines.append(
            f"| {s.scene_id} | {s.estimated_time} | {cell(s.voiceover_script)} | {cell(s.visual_direction)} "
            f"| {cell(s.visual_generation_prompt)} | {cell(s.audio_sfx_cues)} |"
        )
    return "\n".join(lines) + "\n"


def to_csv(record: OutlierRecord) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Cảnh", "Timecode", "Chức năng", "Lời thoại", "Chỉ dẫn dựng hình", "Visual AI Prompt", "Audio / SFX"])
    for s in record.blueprint.production_script:
        writer.writerow([
            s.scene_id, s.estimated_time, s.beat_function, s.voiceover_script,
            s.visual_direction, s.visual_generation_prompt, s.audio_sfx_cues,
        ])
    # BOM để Excel mở đúng tiếng Việt
    return "\ufeff" + buf.getvalue()
