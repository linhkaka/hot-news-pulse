// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Tín hiệu ngầm từ trang YouTube - Most Replayed Heatmap & Transcript
// Tiện ích chạy ngay trên trình duyệt của bạn nên YouTube không chặn như khi gọi từ máy chủ.
// ============================================================================

const HEAT_NEW = /\{"startMillis":"(\d+)","durationMillis":"(\d+)","intensityScoreNormalized":([\d.eE+-]+)/g;
const HEAT_OLD = /"heatMarkerRenderer":\{"timeRangeStartMillis":(\d+),"markerDurationMillis":(\d+),"heatMarkerIntensityScoreNormalized":([\d.eE+-]+)/g;

export function fmtTs(seconds) {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${String(m).padStart(2, "0")}:${sec}`;
}

/** Trả về [[bắt đầu giây, độ dài giây, cường độ 0..1], ...] */
export function parseHeatmap(html) {
  for (const pattern of [HEAT_NEW, HEAT_OLD]) {
    const byStart = new Map();
    for (const m of html.matchAll(pattern)) {
      const start = Number(m[1]) / 1000;
      byStart.set(start, [start, Number(m[2]) / 1000, Math.max(0, Math.min(1, Number(m[3])))]);
    }
    if (byStart.size) return [...byStart.values()].sort((a, b) => a[0] - b[0]);
  }
  return [];
}

function expand(markers, seed, keep, used) {
  let lo = seed;
  let hi = seed;
  while (lo - 1 >= 0 && !used.has(lo - 1) && keep(markers[lo - 1][2])) lo--;
  while (hi + 1 < markers.length && !used.has(hi + 1) && keep(markers[hi + 1][2])) hi++;
  return [lo, hi];
}

/** Đỉnh giữ chân (xem lại nhiều) và vùng trũng (bị tua qua) — cùng thuật toán với Engine. */
export function summarizeHeatmap(markers, maxSpikes = 3, maxDrops = 1) {
  if (markers.length < 5) return { spikes: [], drops: [] };
  const order = (cmp) => [...markers.keys()].sort(cmp);

  const used = new Set();
  const spikes = [];
  for (const idx of order((a, b) => markers[b][2] - markers[a][2])) {
    if (spikes.length >= maxSpikes) break;
    if (used.has(idx) || used.has(idx - 1) || used.has(idx + 1)) continue;
    const peak = markers[idx][2];
    const [lo, hi] = expand(markers, idx, (v) => v >= peak * 0.85, used);
    for (let i = lo - 1; i <= hi + 1; i++) used.add(i);
    spikes.push([lo, hi, peak]);
  }

  const edge = Math.max(1, Math.floor(markers.length / 20));
  const taken = new Set();
  const drops = [];
  const middle = [...markers.keys()].filter((i) => i >= edge && i < markers.length - edge);
  for (const idx of middle.sort((a, b) => markers[a][2] - markers[b][2])) {
    if (drops.length >= maxDrops) break;
    if (taken.has(idx)) continue;
    const low = markers[idx][2];
    let [lo, hi] = expand(markers, idx, (v) => v <= low + 0.05, taken);
    lo = Math.max(lo, edge);
    hi = Math.min(hi, markers.length - edge - 1);
    for (let i = lo - 2; i <= hi + 2; i++) taken.add(i);
    drops.push([lo, hi, low]);
  }

  const toPoint = ([lo, hi, value]) => ({
    time_range: `${fmtTs(markers[lo][0])} - ${fmtTs(markers[hi][0] + markers[hi][1])}`,
    intensity: Math.round(value * 100) / 100,
    note: "",
  });
  spikes.sort((a, b) => a[0] - b[0]);
  return { spikes: spikes.map(toPoint), drops: drops.map(toPoint) };
}

export function heatmapCurve(markers, points = 100) {
  const values = markers.map((m) => m[2]);
  if (values.length <= points) return values.map((v) => Math.round(v * 1000) / 1000);
  const step = values.length / points;
  return Array.from({ length: points }, (_, i) => {
    const a = Math.floor(i * step);
    const b = Math.max(Math.floor((i + 1) * step), a + 1);
    return Math.round(Math.max(...values.slice(a, b)) * 1000) / 1000;
  });
}

/** Lấy danh sách phụ đề (captionTracks) nhúng trong trang xem video. */
export function parseCaptionTracks(html) {
  const m = html.match(/"captionTracks":(\[.*?\])(?:,"audioTracks"|,"translationLanguages")/);
  if (!m) return [];
  try {
    return JSON.parse(m[1]);
  } catch {
    return [];
  }
}

const PREFERRED = ["en", "ja", "ko", "es", "de", "fr", "vi"];

export function pickTrack(tracks) {
  if (!tracks.length) return null;
  const manual = tracks.filter((t) => t.kind !== "asr");
  for (const pool of [manual, tracks]) {
    for (const lang of PREFERRED) {
      const t = pool.find((x) => (x.languageCode || "").startsWith(lang));
      if (t) return t;
    }
  }
  return manual[0] || tracks[0];
}

/** Đổi phụ đề định dạng json3 sang "[mm:ss] câu thoại". */
export function json3ToTranscript(json3, maxChars = 60_000) {
  const lines = [];
  for (const ev of json3.events || []) {
    const text = (ev.segs || []).map((s) => s.utf8 || "").join("").replace(/\s+/g, " ").trim();
    if (text) lines.push(`[${fmtTs((ev.tStartMs || 0) / 1000)}] ${text}`);
  }
  return lines.join("\n").slice(0, maxChars);
}

export async function fetchWatchPage(videoId, fetchImpl = fetch) {
  const res = await fetchImpl(`https://www.youtube.com/watch?v=${videoId}&hl=en`, { credentials: "include" });
  return res.ok ? res.text() : "";
}

export async function fetchTranscript(html, fetchImpl = fetch) {
  const track = pickTrack(parseCaptionTracks(html));
  if (!track?.baseUrl) return "";
  try {
    const url = track.baseUrl.replace(/\\u0026/g, "&");
    const res = await fetchImpl(`${url}&fmt=json3`, { credentials: "include" });
    if (!res.ok) return "";
    const text = await res.text();
    return text ? json3ToTranscript(JSON.parse(text)) : "";
  } catch {
    return "";
  }
}
