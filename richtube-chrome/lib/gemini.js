// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Gemini Key Pool (bản cho Tiện ích Chrome) - xoay vòng key khi hết quota
// ============================================================================

const API = "https://generativelanguage.googleapis.com/v1beta/models";

export function extractJson(text) {
  const cleaned = text.trim().replace(/^```(?:json)?\s*|\s*```$/g, "");
  try {
    return JSON.parse(cleaned);
  } catch {
    const a = cleaned.indexOf("{");
    const b = cleaned.lastIndexOf("}");
    if (a !== -1 && b > a) return JSON.parse(cleaned.slice(a, b + 1));
    throw new Error("Gemini trả về dữ liệu không phải JSON");
  }
}

export class GeminiPool {
  constructor(keys, model, fetchImpl = fetch) {
    this.keys = keys;
    this.model = model;
    // Gọi qua hàm bọc: gọi window.fetch dưới dạng method của object khác sẽ lỗi "Illegal invocation"
    this.fetch = (...args) => fetchImpl(...args);
  }

  async call(key, body) {
    return this.fetch(`${API}/${this.model}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify(body),
    });
  }

  async generateJson(prompt, { videoUrl = null, videoSeconds = 120, temperature = 0.7 } = {}) {
    if (!this.keys.length) throw new Error("Chưa nhập Gemini API key trong Cài đặt");
    const textPart = { text: prompt };
    const parts = videoUrl
      ? [{ fileData: { fileUri: videoUrl, mimeType: "video/*" }, videoMetadata: { startOffset: "0s", endOffset: `${videoSeconds}s` } }, textPart]
      : [textPart];
    const body = {
      contents: [{ role: "user", parts }],
      generationConfig: { temperature, responseMimeType: "application/json" },
    };

    let lastError = "";
    // Bắt đầu từ 1 key ngẫu nhiên để chia đều quota
    const start = Math.floor(Math.random() * this.keys.length);
    const order = [...this.keys.slice(start), ...this.keys.slice(0, start)];
    for (const key of order) {
      let res = await this.call(key, body);
      if (res.status === 400 && videoUrl) {
        // Video riêng tư / quá dài -> chỉ phân tích bằng transcript
        body.contents[0].parts = [textPart];
        videoUrl = null;
        res = await this.call(key, body);
      }
      if ([429, 403, 500, 503].includes(res.status)) {
        lastError = `${res.status}: ${(await res.text()).slice(0, 200)}`;
        continue;
      }
      if (!res.ok) throw new Error(`Gemini lỗi ${res.status}: ${(await res.text()).slice(0, 300)}`);
      const data = await res.json();
      const text = (data.candidates?.[0]?.content?.parts || []).map((p) => p.text || "").join("");
      return extractJson(text);
    }
    throw new Error(`Tất cả Gemini key đều lỗi. Lỗi cuối: ${lastError}`);
  }
}
