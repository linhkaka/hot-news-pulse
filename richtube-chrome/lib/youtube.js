// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: YouTube Data API v3 + VPH / TAE (bản cho Tiện ích Chrome)
// ============================================================================

const API = "https://www.googleapis.com/youtube/v3";
export const MARKETS = ["US", "JP", "KR", "ES", "DE", "FR"];

const VIDEO_PATTERNS = [/[?&]v=([A-Za-z0-9_-]{11})/, /youtu\.be\/([A-Za-z0-9_-]{11})/, /\/(?:shorts|embed|live|v)\/([A-Za-z0-9_-]{11})/];

export function parseVideoId(urlOrId) {
  const s = (urlOrId || "").trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(s)) return s;
  for (const p of VIDEO_PATTERNS) {
    const m = s.match(p);
    if (m) return m[1];
  }
  return null;
}

export function hoursSince(publishedAt, now = new Date()) {
  return Math.max((now - new Date(publishedAt)) / 3_600_000, 1);
}

export function videoVph(video, now) {
  return Number(video.statistics?.viewCount || 0) / hoursSince(video.snippet.publishedAt, now);
}

export function median(values) {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export function baselineVph(videos, excludeId, now) {
  return median(videos.filter((v) => v.id !== excludeId).map((v) => videoVph(v, now)));
}

export function parseDuration(iso) {
  const m = (iso || "").match(/^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/);
  if (!m) return 0;
  const [d, h, mi, s] = m.slice(1).map((x) => Number(x || 0));
  return d * 86400 + h * 3600 + mi * 60 + s;
}

export function bestThumbnail(snippet) {
  const t = snippet.thumbnails || {};
  for (const k of ["maxres", "standard", "high", "medium", "default"]) if (t[k]) return t[k].url;
  return "";
}

export function marketOf(channel) {
  const country = channel?.snippet?.country || "";
  return MARKETS.includes(country) ? country : country || "GLOBAL";
}

export class YouTubeClient {
  constructor(apiKey, fetchImpl = fetch) {
    this.apiKey = apiKey;
    // Gọi qua hàm bọc: gọi window.fetch dưới dạng method của object khác sẽ lỗi "Illegal invocation"
    this.fetch = (...args) => fetchImpl(...args);
  }

  async get(path, params) {
    if (!this.apiKey) throw new Error("Chưa nhập YouTube API key trong Cài đặt");
    const url = new URL(`${API}/${path}`);
    for (const [k, v] of Object.entries({ ...params, key: this.apiKey })) if (v != null) url.searchParams.set(k, v);
    const res = await this.fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(`YouTube API ${path} lỗi ${res.status}: ${data?.error?.message || ""}`);
    return data;
  }

  async videos(ids) {
    const out = [];
    for (let i = 0; i < ids.length; i += 50) {
      const data = await this.get("videos", { part: "snippet,statistics,contentDetails", id: ids.slice(i, i + 50).join(",") });
      out.push(...(data.items || []));
    }
    return out;
  }

  async channel(id) {
    const data = await this.get("channels", { part: "snippet,contentDetails", id });
    if (!data.items?.length) throw new Error(`Không tìm thấy kênh ${id}`);
    return data.items[0];
  }

  async recentUploads(channel, limit = 20) {
    const playlistId = channel.contentDetails.relatedPlaylists.uploads;
    const data = await this.get("playlistItems", { part: "contentDetails", playlistId, maxResults: limit });
    const ids = (data.items || []).map((i) => i.contentDetails.videoId);
    return ids.length ? this.videos(ids) : [];
  }

  async topComments(videoId, limit = 60) {
    try {
      const data = await this.get("commentThreads", {
        part: "snippet", videoId, order: "relevance", maxResults: Math.min(limit, 100), textFormat: "plainText",
      });
      return (data.items || []).map((i) => {
        const c = i.snippet.topLevelComment.snippet;
        return `[${c.likeCount || 0} likes] ${c.textDisplay || ""}`;
      });
    } catch {
      return []; // Bình luận bị tắt
    }
  }
}
