// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Xuất kịch bản .md (giữ giống richtube-engine/richtube/export.py)
// ============================================================================

const cell = (t) => String(t ?? "").replace(/\|/g, "\\|").replace(/\n/g, "<br>");

export function toMarkdown(r) {
  const d = r.deconstruction;
  const b = r.blueprint;
  const lines = [
    `# ${r.title}`,
    "",
    `- Kênh: ${r.channel_name} [${r.market}]`,
    `- Link gốc: ${r.url}`,
    `- TAE: ${r.tae_score}x · ${r.current_vph.toLocaleString("en-US")} VPH (baseline ${r.baseline_vph.toLocaleString("en-US")})`,
    "",
    "## Góc khai thác vượt mặt đối thủ",
    d.exploitable_gaps.superior_angle_proposal,
    "",
    "**Câu hỏi khán giả chưa được giải đáp:**",
    ...d.exploitable_gaps.unanswered_questions.map((q) => `- ${q}`),
    "",
    "## Tiêu đề đề xuất",
    ...b.packaging_blueprint.titles.map((t, i) => `${i + 1}. ${t}`),
    "",
    "## Thumbnail",
  ];
  for (const tc of b.packaging_blueprint.thumbnail_concepts) lines.push(`- Bố cục: ${tc.layout_description}`, `- Prompt: \`${tc.ai_image_prompt}\``, "");
  lines.push(
    "## Kịch bản phân cảnh 4 cột",
    "",
    "| # | Timecode | Lời thoại (Voiceover) | Chỉ dẫn dựng hình | Visual AI Prompt | Audio / SFX |",
    "|---|---|---|---|---|---|",
    ...b.production_script.map(
      (s) => `| ${s.scene_id} | ${s.estimated_time} | ${cell(s.voiceover_script)} | ${cell(s.visual_direction)} | ${cell(s.visual_generation_prompt)} | ${cell(s.audio_sfx_cues)} |`
    )
  );
  return lines.join("\n") + "\n";
}
