// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Prompt mổ xẻ video (giữ giống richtube-engine/richtube/analyzer.py)
// ============================================================================

export const OUTPUT_SHAPE = {
  spike_notes: ["<giải thích vì sao khán giả xem lại đoạn đỉnh #1>", "..."],
  drop_notes: ["<giải thích vì sao khán giả bỏ qua vùng trũng #1>"],
  deconstruction: {
    packaging_analysis: { visual_trigger: "", curiosity_gap: "", psychological_angle: "" },
    hook_30s_breakdown: { opening_mechanism: "", pacing_notes: "", core_loop_opened: "" },
    narrative_beats: [{ time_range: "00:00 - 00:45", beat_name: "", retention_technique: "", structural_purpose: "" }],
    exploitable_gaps: { unanswered_questions: [""], viewer_complaints_or_debates: "", superior_angle_proposal: "" },
  },
  blueprint: {
    packaging_blueprint: { titles: ["", "", ""], thumbnail_concepts: [{ layout_description: "", ai_image_prompt: "" }] },
    production_script: [
      {
        scene_id: 1, estimated_time: "00:00 - 00:07", beat_function: "", voiceover_script: "",
        visual_direction: "", visual_generation_prompt: "", audio_sfx_cues: "",
      },
    ],
  },
};

export function buildPrompt({ title, channel, description, market, stats, spikes, drops, transcript, comments, titleLanguage, scriptLanguage, watchingVideo }) {
  const list = (points) => points.map((p, i) => `#${i + 1} [${p.time_range}] cường độ ${p.intensity}`).join("\n") || "(không có dữ liệu)";
  const videoNote = watchingVideo
    ? "Bạn được xem trực tiếp 2 phút đầu video: hãy đếm số lần cắt cảnh, mô tả âm thanh/nhạc và hình ảnh thật trong 30s đầu."
    : "Bạn không xem được video, hãy suy luận nhịp dựng từ transcript.";

  return `Bạn là Trưởng phòng Chiến lược Nội dung YouTube của Công ty TNHH SNAKEMEDIA.
Nhiệm vụ: mổ xẻ video outlier dưới đây và viết bản đặc tả sản xuất để đội Biên kịch/Editor làm một video VƯỢT MẶT nó
(góc nhìn mới, lấp các lỗ hổng khán giả phàn nàn, KHÔNG sao chép nội dung).

=== THÔNG TIN VIDEO ===
Tiêu đề: ${title}
Kênh: ${channel}
Thị trường: ${market}
Chỉ số: ${stats}
Mô tả: ${(description || "").slice(0, 1500)}

=== MOST REPLAYED HEATMAP ===
Đỉnh giữ chân:
${list(spikes)}
Vùng trũng:
${list(drops)}

=== TRANSCRIPT (có timecode) ===
${transcript || "(không có transcript)"}

=== TOP BÌNH LUẬN ===
${comments.slice(0, 60).join("\n") || "(không có bình luận)"}

=== YÊU CẦU ===
- ${videoNote}
- Mọi phân tích viết bằng tiếng Việt, cụ thể, có timecode, không chung chung.
- spike_notes / drop_notes: đúng số lượng và thứ tự như danh sách đỉnh/vùng trũng ở trên (rỗng nếu không có dữ liệu).
- narrative_beats: 4-8 nhịp bao phủ toàn bộ video.
- exploitable_gaps: rút ra từ bình luận thật; superior_angle_proposal là góc triển khai mới đủ mạnh để làm video riêng.
- titles: đúng 3 phương án, viết bằng ${titleLanguage}, giữ công thức CTR của video gốc nhưng theo góc mới.
- thumbnail_concepts: 1-2 phương án; ai_image_prompt viết bằng tiếng Anh, sẵn sàng dán vào Midjourney/Whisk (thêm --ar 16:9).
- production_script: 8-12 cảnh bao phủ hook và hồi 1 (khoảng 2-3 phút đầu) của video MỚI;
  voiceover_script viết bằng ${scriptLanguage} (có chỉ dẫn giọng trong ngoặc vuông);
  visual_generation_prompt viết bằng tiếng Anh; audio_sfx_cues ghi rõ hiệu ứng và thời điểm.

Chỉ trả về MỘT object JSON đúng cấu trúc sau (thay nội dung mẫu bằng nội dung thật):
${JSON.stringify(OUTPUT_SHAPE, null, 1)}
`;
}

/** Kiểm tra JSON Gemini trả về có đủ các trường Dashboard cần. Trả về thông báo lỗi hoặc null. */
export function validateAnalysis(a) {
  const need = (cond, path) => (cond ? null : `thiếu hoặc sai kiểu: ${path}`);
  const d = a?.deconstruction;
  const b = a?.blueprint;
  return (
    need(d?.packaging_analysis && d?.hook_30s_breakdown, "deconstruction.packaging_analysis / hook_30s_breakdown") ||
    need(Array.isArray(d?.narrative_beats), "deconstruction.narrative_beats") ||
    need(Array.isArray(d?.exploitable_gaps?.unanswered_questions), "deconstruction.exploitable_gaps") ||
    need(Array.isArray(b?.packaging_blueprint?.titles), "blueprint.packaging_blueprint.titles") ||
    need(Array.isArray(b?.packaging_blueprint?.thumbnail_concepts), "blueprint.packaging_blueprint.thumbnail_concepts") ||
    need(Array.isArray(b?.production_script) && b.production_script.length > 0, "blueprint.production_script")
  );
}
