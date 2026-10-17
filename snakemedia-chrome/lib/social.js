// Video viral trên TikTok (tự nhiên + Top Ads) và Facebook Reels (giống snakepod/social.py).
//
// Không có "điểm AI". Một video được dán nhãn bằng luật đọc được:
//   - lượt xem mỗi giờ (vph): ưu tiên tốc độ THẬT giữa 2 lần quét gần nhất, nếu chưa có thì lấy trung bình
//     từ lúc đăng tới giờ;
//   - tuổi video;
//   - tỉ lệ tương tác (thích + bình luận + chia sẻ) / lượt xem và tỉ lệ chia sẻ.
import {C} from "./config.js";
import {classify} from "./pod.js";
import {loadsMany} from "./fbparser.js";

export const PLATFORMS = {tiktok: "TikTok", tiktok_ads: "TikTok Top Ads", fb_reels: "Facebook Reels"};
export const LABELS = {dang_no: "Đang nổ", viral: "Viral", dang_len: "Đang lên", binh_thuong: "Bình thường", top_ads: "Top Ads"};
const HOUR = 3600;
const isObj = v => v !== null && typeof v === "object" && !Array.isArray(v);
const SCRIPT_RE = /<script\b[^>]*\btype="application\/json"[^>]*>([\s\S]*?)<\/script>/g;

function* walk(obj) {
  const stack = [obj];
  while (stack.length) {
    const cur = stack.pop();
    if (isObj(cur)) { yield cur; stack.push(...Object.values(cur)); }
    else if (Array.isArray(cur)) stack.push(...cur);
  }
}

export function toInt(v) {
  if (v === null || v === undefined || typeof v === "boolean") return null;
  if (typeof v === "number") return Number.isFinite(v) ? Math.trunc(v) : null;
  if (isObj(v)) return toInt(v.count);                     // {"count": 123}
  if (typeof v !== "string") return null;
  let s = v.trim().replace(/,/g, "");
  let mult = 1;
  const last = s.slice(-1).toUpperCase();
  if (["K", "M", "B"].includes(last)) { mult = {K: 1e3, M: 1e6, B: 1e9}[last]; s = s.slice(0, -1); }   // "1.2M"
  if (!s.trim()) return null;
  const f = Number(s);
  return Number.isFinite(f) ? Math.trunc(f * mult) : null;
}

const empty = v => v === null || v === undefined || v === "" || (isObj(v) && !Object.keys(v).length);

// Giá trị đầu tiên có khoá trong `keys`, tìm cả trong object con (tối đa `depth` tầng).
function first(d, keys, depth = 3) {
  let level = [d];
  for (let i = 0; i <= depth; i++) {
    const nxt = [];
    for (const cur of level) {
      for (const k of keys) if (isObj(cur) && !empty(cur[k])) return cur[k];
      if (isObj(cur)) nxt.push(...Object.values(cur).filter(isObj));
    }
    level = nxt;
  }
  return null;
}

function textOf(v) {
  if (isObj(v)) v = v.text;
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

function* htmlBlobs(html) {
  for (const m of String(html || "").matchAll(SCRIPT_RE)) {
    try { yield* loadsMany(m[1]); } catch {}
  }
}

const str = v => (typeof v === "string" ? v : null);

// ---------------- TikTok tự nhiên ----------------

export function tiktokItem(d) {
  const stats = isObj(d.stats) ? d.stats : null;
  if (!stats || !("playCount" in stats) || !d.id) return null;
  const st2 = isObj(d.statsV2) ? d.statsV2 : {};
  const pick = k => { const xs = [toInt(stats[k]), toInt(st2[k])].filter(Boolean); return xs.length ? Math.max(...xs) : null; };
  const rawAuthor = d.author;
  const author = isObj(rawAuthor) ? rawAuthor : {};
  const handle = author.uniqueId || str(rawAuthor) || null;
  const video = isObj(d.video) ? d.video : {};
  const itemId = String(d.id);
  return {
    vid: `tiktok:${itemId}`, platform: "tiktok", item_id: itemId,
    url: `https://www.tiktok.com/@${handle || "_"}/video/${itemId}`,
    author: handle || author.nickname || null,
    caption: textOf(d.desc),
    cover_url: video.cover || video.originCover || video.dynamicCover || null,
    video_url: str(video.playAddr),
    views: pick("playCount"), likes: pick("diggCount"), comments: pick("commentCount"),
    shares: pick("shareCount"), saves: pick("collectCount"),
    created_ts: toInt(d.createTime), duration: toInt(video.duration), extra: null,
  };
}

function collectItems(blobs, fn) {
  const out = new Map();
  for (const blob of blobs) for (const d of walk(blob)) { const it = fn(d); if (it) out.set(it.vid, it); }
  return [...out.values()];
}

export const parseTiktokText = text => collectItems(loadsMany(text), tiktokItem);
export const parseTiktokHtml = html => collectItems(htmlBlobs(html), tiktokItem);

// ---------------- TikTok Top Ads (Creative Center) ----------------

export function topadsItem(d) {
  if (!d.ad_title && !d.brand_name) return null;
  const vi = d.video_info;
  if (!isObj(vi) || !d.id) return null;
  let vurl = vi.video_url;
  if (isObj(vurl)) vurl = Object.values(vurl)[0] ?? null;
  const itemId = String(d.id);
  const extra = {};
  for (const k of ["brand_name", "ctr", "cost", "industry_key", "objective_key", "landing_page"])
    if (d[k] !== null && d[k] !== undefined) extra[k] = d[k];
  return {
    vid: `tiktok_ads:${itemId}`, platform: "tiktok_ads", item_id: itemId,
    url: `https://ads.tiktok.com/business/creativecenter/topads/${itemId}/pc/en`,
    author: d.brand_name ?? null, caption: textOf(d.ad_title), cover_url: vi.cover ?? null, video_url: str(vurl),
    views: null, likes: toInt(d.like), comments: toInt(d.comment), shares: toInt(d.share), saves: null,
    created_ts: null, duration: toInt(vi.duration),
    extra: Object.keys(extra).length ? JSON.stringify(extra) : null,
  };
}

export const parseTopadsText = text => collectItems(loadsMany(text), topadsItem);

// ---------------- Facebook Reels (THỬ NGHIỆM) ----------------

// Node video/reel trong GraphQL của Facebook. Cấu trúc hay đổi -> đọc lỏng tay, thiếu gì để trống.
export function reelItem(d) {
  const views = toInt(d.play_count) || toInt(d.video_view_count);
  if (views === null || !d.id) return null;
  const itemId = String(d.post_id || d.id);
  const owner = first(d, ["owner", "video_owner", "actor"]) || {};
  const url = first(d, ["permalink_url", "url", "shareable_url"]);
  const created = toInt(first(d, ["creation_time", "publish_time", "created_time"]));
  let cover = first(d, ["preferred_thumbnail", "thumbnailImage", "first_frame_thumbnail", "image"]);
  if (isObj(cover)) cover = first(cover, ["uri", "url"]);
  const caption = textOf(first(d, ["message", "title", "description", "savable_description"]));
  const videoUrl = first(d, ["playable_url", "browser_native_sd_url"]);
  return {
    vid: `fb_reels:${itemId}`, platform: "fb_reels", item_id: itemId,
    url: str(url) || `https://www.facebook.com/reel/${itemId}`,
    author: isObj(owner) ? owner.name ?? null : null,
    caption, cover_url: str(cover), video_url: str(videoUrl), views,
    likes: toInt(first(d, ["reaction_count", "likers", "unified_reactors"])),
    comments: toInt(first(d, ["comment_count", "total_comment_count"])),
    shares: toInt(first(d, ["share_count", "reshares"])),
    saves: null, created_ts: created,
    duration: toInt(first(d, ["playable_duration_in_ms", "length_in_second"])), extra: null,
  };
}

export const parseReelsText = text => collectItems(loadsMany(text), reelItem);
export const parseReelsHtml = html => collectItems(htmlBlobs(html), reelItem);

// ---------------- Chấm điểm ----------------

function pyRound(x, nd = 0) {
  const k = 10 ** nd, y = x * k, r = Math.round(y);
  return (Math.abs(y % 1) === 0.5 ? 2 * Math.round(y / 2) : r) / k;
}

// Số thực in như Python (1.0 chứ không phải 1)
export const pyNum = x => (Number.isInteger(x) ? x.toFixed(1) : String(x));

export function fmt(n) {
  if (n === null || n === undefined) return "?";
  for (const [div, suf] of [[1e9, "B"], [1e6, "M"], [1e3, "K"]]) if (n >= div) return `${(n / div).toFixed(1)}${suf}`;
  return String(Math.trunc(n));
}

// row: 1 dòng social_videos; snapshots: [[ts, views, likes, comments, shares]] theo thời gian tăng dần
export function summarize(row, snapshots, t = null) {
  t = t || Math.floor(Date.now() / 1000);
  const v = {...row};
  v.extra = row.extra ? JSON.parse(row.extra) : {};
  const ageH = row.created_ts ? (t - row.created_ts) / HOUR : null;
  v.age_days = ageH !== null ? pyRound(ageH / 24, 1) : null;
  const views = row.views ?? null;
  v.avg_vph = views !== null && ageH ? pyRound(views / Math.max(ageH, 1)) : null;

  let recent = null;
  const snaps = snapshots.filter(s => s[1] !== null && s[1] !== undefined);
  if (snaps.length >= 2) {
    const [t0, v0] = snaps[snaps.length - 2], [t1, v1] = snaps[snaps.length - 1];
    if (t1 - t0 >= 600) recent = pyRound(Math.max(0, v1 - v0) / ((t1 - t0) / HOUR));   // 2 lần quét cách nhau >= 10 phút
  }
  v.recent_vph = recent;
  const vph = recent !== null ? recent : v.avg_vph;
  v.vph = vph;

  const inter = (row.likes || 0) + (row.comments || 0) + (row.shares || 0);
  v.engagement = views ? pyRound(100 * inter / views, 2) : null;
  v.share_rate = views ? pyRound(100 * (row.shares || 0) / views, 2) : null;
  v.snapshots = snapshots.slice(-30).map(s => ({ts: s[0], views: s[1], likes: s[2], comments: s[3], shares: s[4]}));

  const checks = [];
  let label;
  if (row.platform === "tiktok_ads") {
    label = "top_ads";
    const ex = v.extra;
    checks.push({ok: true, text: "Nằm trong Top Ads của TikTok Creative Center"});
    if (row.likes !== null && row.likes !== undefined) checks.push({ok: null, text: `${fmt(row.likes)} lượt thích`});
    if (ex.ctr !== null && ex.ctr !== undefined) checks.push({ok: null, text: `CTR: ${ex.ctr}`});
    if (ex.cost !== null && ex.cost !== undefined) checks.push({ok: null, text: `Mức ngân sách: ${ex.cost}`});
  } else {
    const src = recent !== null ? "giữa 2 lần quét gần nhất" : "trung bình từ lúc đăng";
    if (ageH === null || vph === null) checks.push({ok: null, text: "Chưa rõ ngày đăng hoặc lượt xem"});
    else checks.push({ok: null, text: `${fmt(vph)} lượt xem/giờ (${src}), video ${(ageH / 24).toFixed(1)} ngày tuổi`});
    const known = vph !== null && ageH !== null;
    const explode = known && vph >= C.VIRAL_EXPLODE_VPH && ageH <= C.VIRAL_EXPLODE_MAX_DAYS * 24;
    const viral = views !== null && ageH !== null && views >= C.VIRAL_MIN_VIEWS && ageH <= C.VIRAL_MAX_DAYS * 24;
    const rising = known && vph >= C.VIRAL_RISING_VPH && ageH <= C.VIRAL_RISING_MAX_DAYS * 24;
    checks.push({ok: explode, text: `Đang nổ: ≥ ${fmt(C.VIRAL_EXPLODE_VPH)} xem/giờ và ≤ ${C.VIRAL_EXPLODE_MAX_DAYS} ngày`});
    checks.push({ok: viral, text: `Viral: ≥ ${fmt(C.VIRAL_MIN_VIEWS)} xem và ≤ ${C.VIRAL_MAX_DAYS} ngày (${fmt(views)} xem)`});
    checks.push({ok: rising, text: `Đang lên: ≥ ${fmt(C.VIRAL_RISING_VPH)} xem/giờ và ≤ ${C.VIRAL_RISING_MAX_DAYS} ngày`});
    label = explode ? "dang_no" : viral ? "viral" : rising ? "dang_len" : "binh_thuong";
    if (v.engagement !== null) checks.push({ok: null, text: `Tương tác ${pyNum(v.engagement)}% · chia sẻ ${pyNum(v.share_rate)}%`});
  }
  v.label = label;
  v.checks = checks;

  const [productType, niches, personalized] = classify(row.caption || "");
  Object.assign(v, {product_type: productType, niches, personalized, is_pod: !!(productType || personalized)});
  v.sort_vph = vph || 0;
  return v;
}
