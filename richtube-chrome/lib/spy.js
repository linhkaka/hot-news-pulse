// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Quy trình Spy 1 video ngay trên trình duyệt -> bản ghi OutlierRecord
// (cùng cấu trúc với Engine, nên gửi thẳng về Engine/Dashboard được)
// ============================================================================

import { GeminiPool } from "./gemini.js";
import { buildPrompt, validateAnalysis } from "./prompt.js";
import { fetchTranscript, fetchWatchPage, heatmapCurve, parseHeatmap, summarizeHeatmap } from "./signals.js";
import { YouTubeClient, baselineVph, bestThumbnail, hoursSince, marketOf, parseDuration, videoVph } from "./youtube.js";

function jsonString(raw) {
  try {
    return JSON.parse(`"${raw}"`);
  } catch {
    return raw;
  }
}

/** Đọc thông tin cơ bản từ trang xem video (dùng khi chưa có YouTube API key). */
export function parsePageMeta(html) {
  const start = html.indexOf('"videoDetails":{');
  const details = start === -1 ? "" : html.slice(start, start + 20000);
  const str = (key, src = details) => {
    const m = src.match(new RegExp(`"${key}":"((?:[^"\\\\]|\\\\.)*)"`));
    return m ? jsonString(m[1]) : "";
  };
  return {
    title: str("title"),
    channelTitle: str("author"),
    description: str("shortDescription"),
    viewCount: Number(str("viewCount") || 0),
    lengthSeconds: Number(str("lengthSeconds") || 0),
    publishDate: str("publishDate", html) || str("uploadDate", html),
  };
}

export async function spyVideo(videoId, settings, { fetchImpl = fetch, onProgress = () => {} } = {}) {
  const url = `https://www.youtube.com/watch?v=${videoId}`;

  onProgress("Đọc trang YouTube (Most Replayed)...");
  const html = await fetchWatchPage(videoId, fetchImpl).catch(() => "");
  const markers = parseHeatmap(html);
  const { spikes, drops } = summarizeHeatmap(markers);

  onProgress("Lấy lời thoại (transcript)...");
  const transcript = html ? await fetchTranscript(html, fetchImpl) : "";

  let info;
  let comments = [];
  if (settings.youtubeApiKey) {
    onProgress("Lấy số liệu kênh & bình luận (YouTube API)...");
    const yt = new YouTubeClient(settings.youtubeApiKey, fetchImpl);
    const [video] = await yt.videos([videoId]);
    if (!video) throw new Error("Không tìm thấy video (riêng tư hoặc đã xoá?)");
    const channel = await yt.channel(video.snippet.channelId);
    const recent = await yt.recentUploads(channel);
    comments = await yt.topComments(videoId);
    const current = videoVph(video);
    const baseline = baselineVph(recent, videoId);
    info = {
      title: video.snippet.title,
      channelTitle: video.snippet.channelTitle,
      description: video.snippet.description || "",
      thumbnail: bestThumbnail(video.snippet),
      market: marketOf(channel),
      views: Number(video.statistics?.viewCount || 0),
      current,
      baseline,
      tae: baseline > 0 ? Math.round((current / baseline) * 10) / 10 : 0,
      hours: hoursSince(video.snippet.publishedAt),
      duration: parseDuration(video.contentDetails?.duration),
    };
  } else {
    const meta = parsePageMeta(html);
    if (!meta.title) throw new Error("Không đọc được trang video. Hãy nhập YouTube API key trong Cài đặt.");
    const hours = meta.publishDate ? hoursSince(meta.publishDate) : 1;
    info = {
      title: meta.title,
      channelTitle: meta.channelTitle,
      description: meta.description,
      thumbnail: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
      market: "GLOBAL",
      views: meta.viewCount,
      current: meta.viewCount / hours,
      baseline: 0,
      tae: 0, // Cần YouTube API key để so với các video khác của kênh
      hours,
      duration: meta.lengthSeconds,
    };
  }

  onProgress("Gemini đang mổ xẻ video (30-90 giây)...");
  const gemini = new GeminiPool(settings.geminiKeys, settings.geminiModel, fetchImpl);
  let prompt = buildPrompt({
    title: info.title,
    channel: info.channelTitle,
    description: info.description,
    market: info.market,
    stats: `${info.views.toLocaleString("en-US")} views, VPH ${Math.round(info.current)}` +
      (info.baseline ? `, baseline kênh ${Math.round(info.baseline)} VPH, TAE ${info.tae}x` : ""),
    spikes,
    drops,
    transcript,
    comments,
    titleLanguage: settings.titleLanguage,
    scriptLanguage: settings.scriptLanguage,
    watchingVideo: settings.watchVideo,
  });

  let analysis;
  for (let attempt = 0; attempt < 2; attempt++) {
    analysis = await gemini.generateJson(prompt, { videoUrl: settings.watchVideo ? url : null });
    const problem = validateAnalysis(analysis);
    if (!problem) break;
    if (attempt === 1) throw new Error(`Gemini trả JSON sai cấu trúc 2 lần: ${problem}`);
    prompt += `\n\nLẦN TRƯỚC BẠN TRẢ SAI CẤU TRÚC (${problem}). Hãy trả lại JSON đúng cấu trúc.`;
  }

  spikes.forEach((p, i) => (p.note = analysis.spike_notes?.[i] || ""));
  drops.forEach((p, i) => (p.note = analysis.drop_notes?.[i] || ""));

  return {
    video_id: videoId,
    title: info.title,
    channel_name: info.channelTitle,
    market: info.market,
    url,
    thumbnail_url: info.thumbnail,
    tae_score: info.tae,
    current_vph: Math.round(info.current),
    baseline_vph: Math.round(info.baseline),
    published_hours_ago: Math.round(info.hours),
    lark_synced: false,
    lark_record_id: null,
    analyzed_at: new Date().toISOString(),
    duration_seconds: info.duration,
    heatmap_curve: heatmapCurve(markers),
    heatmap_peaks: { retention_spikes: spikes, retention_drops: drops },
    deconstruction: analysis.deconstruction,
    blueprint: analysis.blueprint,
  };
}

/** Gửi kết quả về RICHTUBE Engine (đồng bộ Lark + báo Telegram + hiện trên Dashboard). */
export async function pushToEngine(record, settings, fetchImpl = fetch) {
  const base = settings.engineUrl.replace(/\/+$/, "");
  const res = await fetchImpl(`${base}/api/v1/outliers/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(settings.engineApiKey ? { "X-API-Key": settings.engineApiKey } : {}),
    },
    body: JSON.stringify(record),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`Engine lỗi ${res.status}: ${typeof data.detail === "string" ? data.detail : "không rõ"}`);
  return data;
}
