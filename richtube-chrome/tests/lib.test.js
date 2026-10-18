import assert from "node:assert/strict";
import { test } from "node:test";

import { toMarkdown } from "../lib/export.js";
import { GeminiPool, extractJson } from "../lib/gemini.js";
import { validateAnalysis } from "../lib/prompt.js";
import { json3ToTranscript, heatmapCurve, parseCaptionTracks, parseHeatmap, pickTrack, summarizeHeatmap } from "../lib/signals.js";
import { parsePageMeta, pushToEngine, spyVideo } from "../lib/spy.js";
import { baselineVph, parseDuration, parseVideoId, videoVph } from "../lib/youtube.js";

const VID = "dQw4w9WgXcQ";
const NOW = new Date("2026-10-17T00:00:00Z");

export function sampleAnalysis(spikes = 0, drops = 0) {
  return {
    spike_notes: Array.from({ length: spikes }, (_, i) => `spike note ${i}`),
    drop_notes: Array.from({ length: drops }, (_, i) => `drop note ${i}`),
    deconstruction: {
      packaging_analysis: { visual_trigger: "vt", curiosity_gap: "cg", psychological_angle: "pa" },
      hook_30s_breakdown: { opening_mechanism: "om", pacing_notes: "pn", core_loop_opened: "cl" },
      narrative_beats: [{ time_range: "00:00 - 00:45", beat_name: "Hook", retention_technique: "Paradox", structural_purpose: "p" }],
      exploitable_gaps: { unanswered_questions: ["Q1"], viewer_complaints_or_debates: "debate", superior_angle_proposal: "Góc mới" },
    },
    blueprint: {
      packaging_blueprint: { titles: ["T1", "T2", "T3"], thumbnail_concepts: [{ layout_description: "ld", ai_image_prompt: "prompt --ar 16:9" }] },
      production_script: [{ scene_id: 1, estimated_time: "00:00 - 00:07", beat_function: "Hook", voiceover_script: "vo | x", visual_direction: "vd", visual_generation_prompt: "vgp", audio_sfx_cues: "sfx" }],
    },
  };
}

const heatHtml = (values) =>
  values.map((v, i) => `{"startMillis":"${i * 10000}","durationMillis":"10000","intensityScoreNormalized":${v}},`).join("");

test("parseVideoId", () => {
  for (const u of [VID, `https://www.youtube.com/watch?v=${VID}`, `https://youtu.be/${VID}?si=x`, `https://www.youtube.com/shorts/${VID}`]) {
    assert.equal(parseVideoId(u), VID);
  }
  assert.equal(parseVideoId("https://www.youtube.com/@abc"), null);
});

test("VPH, baseline, duration", () => {
  const v = (id, views) => ({ id, snippet: { publishedAt: "2026-10-16T14:00:00Z" }, statistics: { viewCount: String(views) } });
  assert.equal(videoVph(v("a", 1000), NOW), 100);
  assert.equal(baselineVph([v("a", 1000), v("b", 100), v("c", 200), v("d", 300)], "a", NOW), 20);
  assert.equal(parseDuration("PT1H2M3S"), 3723);
  assert.equal(parseDuration(""), 0);
});

test("heatmap: giống hệt kết quả của Engine (Python)", () => {
  const values = [1.0, 0.9, 0.5, 0.4, 0.4, 0.8, 0.4, 0.4, 0.05, 0.06, 0.4, 0.4, 0.7, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.3];
  const { spikes, drops } = summarizeHeatmap(parseHeatmap(heatHtml(values)));
  assert.deepEqual(spikes.map((s) => s.time_range), ["00:00 - 00:20", "00:50 - 01:00", "02:00 - 02:10"]);
  assert.equal(drops.length, 1);
  assert.equal(drops[0].time_range, "01:20 - 01:40");
  assert.deepEqual(
    parseHeatmap('"heatMarkerRenderer":{"timeRangeStartMillis":0,"markerDurationMillis":5000,"heatMarkerIntensityScoreNormalized":0.3}'),
    [[0, 5, 0.3]]
  );
  const big = Array.from({ length: 250 }, (_, i) => [i, 1, i === 123 ? 0.9 : 0.1]);
  const curve = heatmapCurve(big);
  assert.equal(curve.length, 100);
  assert.equal(Math.max(...curve), 0.9);
});

test("caption tracks & json3 transcript", () => {
  const html = `..."captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext?v=x\\u0026lang=en","languageCode":"en","kind":"asr"},{"baseUrl":"https://y/ja","languageCode":"ja"}],"audioTracks":[]...`;
  const tracks = parseCaptionTracks(html);
  assert.equal(tracks.length, 2);
  assert.equal(pickTrack(tracks).languageCode, "ja"); // ưu tiên phụ đề người làm hơn phụ đề tự động
  const text = json3ToTranscript({ events: [{ tStartMs: 65000, segs: [{ utf8: "Hello " }, { utf8: "world" }] }, { tStartMs: 0 }] });
  assert.equal(text, "[01:05] Hello world");
});

test("parsePageMeta (không cần YouTube API key)", () => {
  const html = `{"videoDetails":{"videoId":"${VID}","title":"Chip \\"War\\"","lengthSeconds":"600","shortDescription":"desc","viewCount":"12345","author":"Magnates"}},"publishDate":"2026-10-15T10:00:00-07:00"`;
  const meta = parsePageMeta(html);
  assert.equal(meta.title, 'Chip "War"');
  assert.equal(meta.channelTitle, "Magnates");
  assert.equal(meta.viewCount, 12345);
  assert.equal(meta.lengthSeconds, 600);
  assert.equal(meta.publishDate, "2026-10-15T10:00:00-07:00");
});

test("extractJson & validateAnalysis", () => {
  assert.deepEqual(extractJson('```json\n{"a":1}\n```'), { a: 1 });
  assert.deepEqual(extractJson('Here: {"a":2} done'), { a: 2 });
  assert.equal(validateAnalysis(sampleAnalysis()), null);
  assert.match(validateAnalysis({ wrong: 1 }), /thiếu/);
});

const geminiReply = (payload) =>
  new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: JSON.stringify(payload) }] } }] }), { status: 200 });

test("GeminiPool: chuyển key khi hết quota, bỏ video khi bị 400", async () => {
  const calls = [];
  const fakeFetch = async (_url, init) => {
    const key = init.headers["x-goog-api-key"];
    const hasVideo = init.body.includes("fileData");
    calls.push([key, hasVideo]);
    if (key === "bad") return new Response("quota", { status: 429 });
    if (hasVideo) return new Response("unsupported", { status: 400 });
    return geminiReply({ ok: true });
  };
  const pool = new GeminiPool(["bad", "good"], "m", fakeFetch);
  const orig = Math.random;
  Math.random = () => 0; // bắt đầu từ key "bad"
  try {
    assert.deepEqual(await pool.generateJson("hi", { videoUrl: "https://youtu.be/x" }), { ok: true });
  } finally {
    Math.random = orig;
  }
  assert.deepEqual(calls, [["bad", true], ["good", true], ["good", false]]);
  await assert.rejects(new GeminiPool([], "m", fakeFetch).generateJson("x"), /Gemini API key/);
});

function fakeYouTube({ withApi }) {
  const hours = (h) => new Date(Date.now() - h * 3_600_000).toISOString();
  const video = (id, views, h) => ({
    id,
    snippet: { title: `Video ${id}`, channelId: "UCx", channelTitle: "Magnates", description: "d", publishedAt: hours(h), thumbnails: { high: { url: `https://i.ytimg.com/vi/${id}/hq.jpg` } } },
    statistics: { viewCount: String(views) },
    contentDetails: { duration: "PT10M" },
  });
  const videos = { [VID]: video(VID, 50000, 10), aaaaaaaaaaa: video("aaaaaaaaaaa", 20000, 100) };
  const watchHtml =
    heatHtml([1, 0.4, 0.4, 0.8, 0.4, 0.05, 0.4, 0.4, 0.6, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]) +
    `"captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext?v=${VID}","languageCode":"en"}],"audioTracks":[]` +
    `{"videoDetails":{"videoId":"${VID}","title":"Page Title","lengthSeconds":"200","shortDescription":"s","viewCount":"5000","author":"PageAuthor"}},"publishDate":"${hours(5)}"`;
  const geminiBodies = [];

  const fetchImpl = async (input, init = {}) => {
    const url = String(input);
    if (url.startsWith("https://www.youtube.com/watch")) return new Response(watchHtml);
    if (url.includes("/api/timedtext")) return new Response(JSON.stringify({ events: [{ tStartMs: 0, segs: [{ utf8: "If this factory disappeared" }] }] }));
    if (url.includes("generativelanguage")) {
      geminiBodies.push(JSON.parse(init.body));
      return geminiReply(sampleAnalysis(3, 1));
    }
    if (!withApi) throw new Error(`unexpected ${url}`);
    const u = new URL(url);
    if (u.pathname.endsWith("/videos")) return new Response(JSON.stringify({ items: u.searchParams.get("id").split(",").map((i) => videos[i]).filter(Boolean) }));
    if (u.pathname.endsWith("/channels")) return new Response(JSON.stringify({ items: [{ id: "UCx", snippet: { country: "US" }, contentDetails: { relatedPlaylists: { uploads: "UUx" } } }] }));
    if (u.pathname.endsWith("/playlistItems")) return new Response(JSON.stringify({ items: Object.keys(videos).map((v) => ({ contentDetails: { videoId: v } })) }));
    if (u.pathname.endsWith("/commentThreads")) return new Response(JSON.stringify({ items: [{ snippet: { topLevelComment: { snippet: { likeCount: 900, textDisplay: "You forgot Zeiss!" } } } }] }));
    throw new Error(`unexpected ${url}`);
  };
  return { fetchImpl, geminiBodies };
}

const SETTINGS = { geminiKeys: ["k"], geminiModel: "m", watchVideo: true, titleLanguage: "English", scriptLanguage: "Tiếng Việt" };

test("spyVideo: đầy đủ với YouTube API key", async () => {
  const { fetchImpl, geminiBodies } = fakeYouTube({ withApi: true });
  const progress = [];
  const r = await spyVideo(VID, { ...SETTINGS, youtubeApiKey: "yt" }, { fetchImpl, onProgress: (p) => progress.push(p) });
  assert.equal(r.market, "US");
  assert.equal(r.current_vph, 5000);
  assert.equal(r.baseline_vph, 200);
  assert.equal(r.tae_score, 25);
  assert.equal(r.duration_seconds, 600);
  assert.equal(r.heatmap_curve.length, 20);
  assert.deepEqual(r.heatmap_peaks.retention_spikes.map((p) => p.note), ["spike note 0", "spike note 1", "spike note 2"]);
  assert.equal(r.heatmap_peaks.retention_drops[0].note, "drop note 0");
  const parts = geminiBodies[0].contents[0].parts;
  assert.equal(parts[0].fileData.fileUri, `https://www.youtube.com/watch?v=${VID}`);
  assert.match(parts[1].text, /You forgot Zeiss!/);
  assert.match(parts[1].text, /If this factory disappeared/);
  assert.ok(progress.length >= 3);
});

test("spyVideo: chạy được khi chưa có YouTube API key (TAE = 0)", async () => {
  const { fetchImpl } = fakeYouTube({ withApi: false });
  const r = await spyVideo(VID, { ...SETTINGS, youtubeApiKey: "", watchVideo: false }, { fetchImpl });
  assert.equal(r.title, "Page Title");
  assert.equal(r.channel_name, "PageAuthor");
  assert.equal(r.tae_score, 0);
  assert.equal(r.duration_seconds, 200);
  assert.ok(r.current_vph > 0);
});

test("spyVideo: báo lỗi khi Gemini trả JSON sai 2 lần", async () => {
  let n = 0;
  const fetchImpl = async (input) => {
    const url = String(input);
    if (url.includes("generativelanguage")) {
      n++;
      return geminiReply({ wrong: true });
    }
    return fakeYouTube({ withApi: true }).fetchImpl(input);
  };
  await assert.rejects(spyVideo(VID, { ...SETTINGS, youtubeApiKey: "yt" }, { fetchImpl }), /sai cấu trúc 2 lần/);
  assert.equal(n, 2);
});

test("pushToEngine gửi kèm X-API-Key và báo lỗi rõ ràng", async () => {
  const seen = [];
  const ok = async (url, init) => {
    seen.push([url, init.headers["X-API-Key"]]);
    return new Response(JSON.stringify({ video_id: VID, lark_synced: true }), { status: 200 });
  };
  const saved = await pushToEngine({ video_id: VID }, { engineUrl: "http://localhost:8000/", engineApiKey: "k" }, ok);
  assert.equal(saved.lark_synced, true);
  assert.deepEqual(seen[0], ["http://localhost:8000/api/v1/outliers/import", "k"]);
  const bad = async () => new Response(JSON.stringify({ detail: "Sai hoặc thiếu X-API-Key" }), { status: 401 });
  await assert.rejects(pushToEngine({}, { engineUrl: "http://x" }, bad), /401: Sai hoặc thiếu X-API-Key/);
});

test("toMarkdown giống bản của Engine", () => {
  const md = toMarkdown({
    title: "T", channel_name: "c", market: "US", url: "u", tae_score: 3.2, current_vph: 12000, baseline_vph: 3000, ...sampleAnalysis(),
  });
  assert.match(md, /TAE: 3.2x · 12,000 VPH \(baseline 3,000\)/);
  assert.match(md, /\| 1 \| 00:00 - 00:07 \| vo \\\| x \| vd \| vgp \| sfx \|/);
});
