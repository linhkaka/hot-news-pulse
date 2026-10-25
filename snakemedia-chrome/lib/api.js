// Các "đường dẫn API" giống hệt bản app (snakepod/server.py), nhưng chạy trong phần nền của tiện ích.
// Trang giao diện gửi {type: "api", method, path, body} qua chrome.runtime.sendMessage.
import {C, URLS} from "./config.js";
import * as db from "./db.js";
import * as diag from "./diag.js";
import * as jobs from "./jobs.js";
import * as notify from "./notify.js";
import * as safety from "./safety.js";
import * as social from "./social.js";
import * as demo from "./demo.js";
import * as media from "./media.js";
import * as shopify from "./shopify.js";
import * as kwtrends from "./kwtrends.js";

export class HttpError extends Error {
  constructor(status, detail) { super(detail); this.status = status; }
}

const LABELS = {sap_win: "Sắp WIN", win: "Video Win", scale: "Video scale", theo_doi: "Chờ thêm dữ liệu",
  trang_cu: "Trang bán cũ", cu: "Video già"};
const DAY = 86400;

const routes = [];
function route(method, pattern, fn) {
  const re = new RegExp("^" + pattern.replace(/\{(\w+)(:path)?\}/g, (_, n, p) => (p ? `(?<${n}>.+)` : `(?<${n}>[^/]+)`)) + "$");
  routes.push({method, re, fn});
}

export async function handle({method = "GET", path, body = null}) {
  const [p, query] = String(path).split("?");
  for (const r of routes) {
    if (r.method !== method) continue;
    const m = r.re.exec(p);
    if (!m) continue;
    const params = Object.fromEntries(Object.entries(m.groups || {}).map(([k, v]) => [k, decodeURIComponent(v)]));
    try {
      return {ok: true, status: 200, data: await r.fn({params, q: new URLSearchParams(query || ""), body: body || {}})};
    } catch (e) {
      if (e instanceof HttpError) return {ok: false, status: e.status, detail: e.message};
      console.error(e);
      return {ok: false, status: 500, detail: String(e && e.message || e)};
    }
  }
  return {ok: false, status: 404, detail: "Not Found"};
}

// ---- đọc tham số ----
const bool = (q, k, d = false) => (q.has(k) ? ["true", "1", "yes", "on"].includes(q.get(k).toLowerCase()) : d);
const int = (q, k, d) => { const v = parseInt(q.get(k), 10); return Number.isFinite(v) ? v : d; };
const str = (q, k) => q.get(k) || null;
const need = (cond, msg, status = 400) => { if (!cond) throw new HttpError(status, msg); };

function pageOf(items, offset, limit) {
  limit = Math.max(1, Math.min(limit, 200));
  offset = Math.max(0, offset);
  return items.slice(offset, offset + limit);
}

function facets(items) {
  const types = new Map(), niches = new Map();
  for (const v of items) {
    if (v.product_type) types.set(v.product_type, (types.get(v.product_type) || 0) + 1);
    for (const n of v.niches || []) niches.set(n, (niches.get(n) || 0) + 1);
  }
  const order = m => [...m].map(([name, count]) => ({name, count})).sort((a, b) => b.count - a.count);
  return {product_types: order(types), niches: order(niches)};
}

// Ảnh lưu trong tiện ích -> gắn thẳng vào kết quả (data URL) để trang giao diện hiện được
async function withThumbs(items, field, out) {
  const data = await db.thumbData(items.map(v => v[field]));
  for (const v of items) v[out] = data[v[field]] || null;
  return items;
}

const clean = v => { const {_rank, ...rest} = v; return rest; };

// ---------------- tổng quan + video QC Facebook ----------------

const hasMark = (mk, cid, kind) => !!(mk[cid] && mk[cid].has(kind));

route("GET", "/api/stats", async () => {
  const counts = await db.labelCounts();
  const [vids, mk] = await Promise.all([db.listVideos(), db.marks()]);
  const shown = vids.filter(v => !hasMark(mk, v.cid, "hidden"));
  const ms = Object.values(mk);
  const tabs = {potential: shown.filter(v => v.potential).length, cow: shown.filter(v => v.cash_cow).length,
    test: ms.filter(m => m.has("test")).length, hidden: ms.filter(m => m.has("hidden")).length,
    dig: (await jobs.digCandidates()).length, stores: (await jobs.storeRows()).filter(r => r.status === "pending").length};
  return {labels: Object.entries(LABELS).map(([key, name]) => ({key, name, count: counts[key] || 0})),
    total: Object.values(counts).reduce((s, n) => s + n, 0), tabs, scans: await db.listScans(10), now: db.now()};
});

const TAB_SORTS = {potential: v => [v.ads_new_48h || 0, v.ads_per_day], cow: v => [v.buckets.old, v.ads_per_day],
  // Video nổi bật (Tổng quan): video mới nhất trước, nhiều shop đang chạy trước
  hot: v => [-(v.video_age_days ?? 9999), v.shops_active]};
const cmpDesc = (x, y) => { for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return y[i] - x[i]; return 0; };

// Gắn đánh dấu (Video test / Đã ẩn), lần đào gần nhất và thay đổi so với hôm trước (lịch sử theo dõi).
async function decorate(items) {
  const [mk, dug, hist, clones] = await Promise.all([db.marks(), db.digs(), db.history(items.map(v => v.cid), 2),
    db.getSetting("clones", {})]);
  for (const v of items) {
    v.marks = [...(mk[v.cid] || [])].sort();
    v.dug_ts = dug[v.cid] ?? null;
    v.clone = clones[v.cid] ?? null;
    const h = hist[v.cid] || [];
    v.delta = h.length >= 2 ? Object.fromEntries(["pages_active", "shops_active", "shops_win", "scale", "urls"].map(k => [k, h[0][k] - h[1][k]])) : null;
  }
  return items;
}

// Link tìm nguồn hàng (C.SOURCING): theo tên sản phẩm và theo ảnh.
function sourcingLinks(v) {
  const words = (v.product_key || "").replace(/-/g, " ") || (v.title || "").split(/\s+/).filter(Boolean).slice(0, 8).join(" ");
  const plus = x => encodeURIComponent(x).replace(/%20/g, "+");
  const q = plus(words), image = plus(v.thumb_url || "");
  return C.SOURCING.filter(([, t]) => q && (!t.includes("{image}") || image))
    .map(([name, t]) => ({name, url: t.replace("{q}", q).replace("{image}", image)}));
}

route("GET", "/api/videos", async ({q}) => {
  let items = (await db.listVideos(str(q, "label"))).map(clean);
  const mk = await db.marks(), tab = str(q, "tab");
  items = items.filter(v => hasMark(mk, v.cid, "hidden") === (tab === "hidden"));
  if (tab === "test") items = items.filter(v => hasMark(mk, v.cid, "test"));
  else if (tab === "potential") items = items.filter(v => v.potential);
  else if (tab === "cow") items = items.filter(v => v.cash_cow);
  else if (tab === "hot") items = items.filter(v => ["sap_win", "win", "scale"].includes(v.label) || v.potential);
  else if (tab === "dig") items = (await jobs.digCandidates()).map(clean);
  if (tab in TAB_SORTS) items.sort((a, b) => cmpDesc(TAB_SORTS[tab](a), TAB_SORTS[tab](b)));
  if (bool(q, "spread"))   // QC Facebook đang lan nhanh: xếp theo số QC mới 48h
    items = items.filter(v => v.spreading)
      .sort((a, b) => ((b.ads_new_48h || 0) - (a.ads_new_48h || 0)) || ((b.shops_new_48h || 0) - (a.shops_new_48h || 0)));
  const text = str(q, "q");
  if (text) {
    const ql = text.toLowerCase();
    items = items.filter(v => (v.title || "").toLowerCase().includes(ql) || v.shops.some(s => s.includes(ql))
      || v.keywords.some(k => k.toLowerCase().includes(ql)));
  }
  if (bool(q, "pod")) items = items.filter(v => v.is_pod);
  if (str(q, "page_id")) items = items.filter(v => v.page_ids.includes(q.get("page_id")));
  if (str(q, "shop")) items = items.filter(v => v.shops.includes(q.get("shop")));
  if (str(q, "product")) items = items.filter(v => v.product_key === q.get("product"));
  const f = facets(items);
  if (str(q, "product_type")) items = items.filter(v => v.product_type === q.get("product_type"));
  if (str(q, "niche")) items = items.filter(v => (v.niches || []).includes(q.get("niche")));
  const page = pageOf(items, int(q, "offset", 0), int(q, "limit", 60)).map(({ads, ...v}) => v);
  await withThumbs(page, "thumb", "thumb_src");
  return {items: await decorate(page), total: items.length, offset: Math.max(0, int(q, "offset", 0)), facets: f};
});

route("GET", "/api/videos/{cid}", async ({params}) => {
  const v = await db.getVideo(params.cid);
  need(v, "Not Found", 404);
  const followed = new Set((await db.listFollows()).map(f => f.kind + "\u0000" + f.key));
  const names = {};
  for (const a of v.ads) if (!(a.page_id in names)) names[a.page_id] = a.page_name || a.page_id;
  v.page_list = v.page_ids.map(p => ({id: p, name: names[p] || p, followed: followed.has("page\u0000" + p)}));
  v.shop_list = v.shops.map(d => ({domain: d, followed: followed.has("shop\u0000" + d)}));
  await withThumbs([v], "thumb", "thumb_src");
  await decorate([v]);
  v.history = (await db.history([v.cid], C.HISTORY_DAYS))[v.cid];
  v.sourcing = sourcingLinks(v);
  v.clone_url = cloneUrl(v);
  v.media = {video_url: v.video_url, image_url: v.thumb_url, video_expires_ts: media.linkExpiry(v.video_url),
    video_expired: media.expired(v.video_url), variants: new Set(v.ads.map(a => a.video_url).filter(Boolean)).size};
  return clean(v);
});

route("POST", "/api/videos/{cid}/dig", async ({params, q}) => {
  const v = await db.getVideo(params.cid);
  need(v, "Not Found", 404);
  jobs.submit("dig", `Đào sâu '${v.title.slice(0, 40)}'`, {cid: params.cid, country: q.get("country") || C.DEFAULT_COUNTRY});
  return {ok: true};
});

route("POST", "/api/scan", async ({body}) => {
  const kws = [...new Set([body.keyword, ...(body.keywords || [])].map(k => String(k || "").trim()).filter(Boolean))];
  need(kws.length, "Thiếu từ khoá");
  const country = String(body.country || C.DEFAULT_COUNTRY).toUpperCase();
  const maxAds = Math.max(10, Math.min(+body.max_ads || C.DEFAULT_MAX_ADS, 2000));
  let queued = 0;
  for (const kw of kws.slice(0, 200)) {
    if (body.save) await db.addWatchKeyword(kw, country);
    queued += jobs.submit("keyword", `Quét '${kw}'`, {keyword: kw, country, max_ads: maxAds});
  }
  return {ok: true, queued};
});

route("GET", "/api/keywords/suggest", () => jobs.keywordSuggestions());

route("POST", "/api/marks", async ({body}) => {
  need(["test", "hidden"].includes(body.kind), "kind phải là 'test' hoặc 'hidden'");
  await db.setMark(String(body.cid), body.kind, body.on ?? true);
  return {ok: true};
});

route("POST", "/api/dig/batch", async ({body}) => {
  let n = 0;
  for (const v of (await jobs.digCandidates()).slice(0, Math.max(1, Math.min(+body.n || 10, 50))))
    n += jobs.submit("dig", `Đào sâu '${v.title.slice(0, 40)}'`, {cid: v.cid, country: C.DEFAULT_COUNTRY});
  return {queued: n};
});

route("GET", "/api/stores", async ({q}) => {
  let rows = await jobs.storeRows();
  const cut = db.now() - C.STORE_FRESH_DAYS * DAY;
  const summary = {total: rows.length, pending: rows.filter(r => r.status === "pending").length,
    done: rows.filter(r => r.status === "done").length,
    new_videos_7d: rows.filter(r => (r.swept_ts || 0) >= cut).reduce((s, r) => s + (r.new_videos || 0), 0),
    auto: await jobs.autoSettings()};
  const status = q.get("status") || "pending";
  if (["pending", "done"].includes(status)) rows = rows.filter(r => r.status === status);
  return {items: pageOf(rows, int(q, "offset", 0), int(q, "limit", 50)), total: rows.length,
    offset: Math.max(0, int(q, "offset", 0)), summary};
});

route("POST", "/api/stores/sweep", async ({body}) => {
  const domains = (body.domains && body.domains.length) ? body.domains
    : (await jobs.storeRows()).filter(r => r.status === "pending").slice(0, Math.max(1, Math.min(+body.n || 10, 100))).map(r => r.domain);
  return {queued: jobs.queueSweeps(domains)};
});

route("GET", "/api/export", () => db.exportData());

route("POST", "/api/import", async ({body}) => {
  let ads, lands;
  try { [ads, lands] = await db.importData(body); } catch (e) {
    if (e instanceof RangeError) throw new HttpError(400, e.message);
    throw e;
  }
  jobs.submit("passive", "Gộp kho + chấm lại", {});
  return {ads, landings: lands};
});

// Bảng niche: niche nào đang có nhiều video Sắp WIN / Win / Scale.
route("GET", "/api/niches", async ({q}) => {
  const onlyPod = bool(q, "pod", true);
  const rows = new Map();
  for (const v of await db.listVideos()) {
    if (onlyPod && !v.is_pod) continue;
    for (const n of (v.niches && v.niches.length ? v.niches : ["(chưa rõ niche)"])) {
      if (!rows.has(n)) rows.set(n, {niche: n, sap_win: 0, win: 0, scale: 0, total: 0, ads_per_day: 0, types: {}, top: null});
      const r = rows.get(n);
      r.total += 1;
      if (["sap_win", "win", "scale"].includes(v.label)) r[v.label] += 1;
      r.ads_per_day += v.ads_per_day;
      if (v.product_type) r.types[v.product_type] = (r.types[v.product_type] || 0) + 1;
      if (["sap_win", "win"].includes(v.label) && (!r.top || v.ads_per_day > r.top.ads_per_day))
        r.top = {cid: v.cid, title: v.title, ads_per_day: v.ads_per_day};
    }
  }
  const key = r => [r.sap_win + r.win, r.scale, r.ads_per_day];
  const out = [...rows.values()].sort((a, b) => {
    const x = key(a), y = key(b);
    for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return y[i] - x[i];
    return 0;
  });
  for (const r of out) {
    r.ads_per_day = Math.round(r.ads_per_day * 100) / 100;
    r.types = Object.keys(r.types).sort((a, b) => r.types[b] - r.types[a]).slice(0, 3);
  }
  return out;
});

// ---------------- video viral: TikTok / TikTok Top Ads / Facebook Reels ----------------

async function socialList(platform = null) {
  const rows = await db.socialRows(platform);
  const snaps = await db.socialSnapshots(new Set(rows.map(r => r.vid)));
  return rows.map(r => social.summarize(r, snaps[r.vid] || []));
}

const SOCIAL_SORTS = {vph: v => v.sort_vph, views: v => v.views || 0, likes: v => v.likes || 0,
  engagement: v => v.engagement || 0, new: v => v.created_ts || v.first_seen || 0};

route("GET", "/api/viral", async ({q}) => {
  let items = await socialList(str(q, "platform"));
  const markets = {};
  for (const v of items) if (v.market) markets[v.market] = (markets[v.market] || 0) + 1;
  if (str(q, "market")) items = items.filter(v => v.market === q.get("market"));
  const counts = Object.fromEntries(Object.keys(social.LABELS).map(k => [k, 0]));
  for (const v of items) counts[v.label] += 1;
  if (str(q, "label")) items = items.filter(v => v.label === q.get("label"));
  const text = str(q, "q");
  if (text) {
    const ql = text.toLowerCase();
    items = items.filter(v => (v.caption || "").toLowerCase().includes(ql) || (v.author || "").toLowerCase().includes(ql)
      || (v.keyword || "").toLowerCase().includes(ql));
  }
  if (bool(q, "pod")) items = items.filter(v => v.is_pod);
  const f = facets(items);
  if (str(q, "product_type")) items = items.filter(v => v.product_type === q.get("product_type"));
  if (str(q, "niche")) items = items.filter(v => v.niches.includes(q.get("niche")));
  const sortKey = SOCIAL_SORTS[q.get("sort")] || SOCIAL_SORTS.vph;
  items.sort((a, b) => sortKey(b) - sortKey(a));
  const page = pageOf(items, int(q, "offset", 0), int(q, "limit", 60)).map(({snapshots, ...v}) => v);
  await withThumbs(page, "cover_path", "cover_src");
  return {items: page, total: items.length, offset: Math.max(0, int(q, "offset", 0)), facets: f, counts,
    labels: social.LABELS, platforms: social.PLATFORMS, markets};
});

route("GET", "/api/viral/keywords", () => db.listSocialWatch());

route("DELETE", "/api/viral/keywords/{platform}/{keyword}", async ({params, q}) => {
  // Top Ads không từ khoá được gửi là " "; không có ?country = bỏ ở mọi thị trường
  await db.removeSocialWatch(params.platform, params.keyword.trim(), q.has("country") ? q.get("country") : null);
  return {ok: true};
});

route("GET", "/api/markets", () => ({markets: C.MARKETS, sources: social.SOURCES, market_sources: [...social.MARKET_SOURCES].sort()}));

route("POST", "/api/viral/scan", async ({body}) => {
  need(body.platform in social.SOURCES, "Nền tảng không hợp lệ");
  let kws = [...new Set([body.keyword, ...(body.keywords || [])].map(k => String(k || "").trim()).filter(Boolean))];
  const byMarket = social.MARKET_SOURCES.has(body.platform);
  if (!kws.length) { need(byMarket, "Thiếu từ khoá"); kws = [""]; }
  let countries = [...new Set((body.countries || []).map(c => String(c).trim().toUpperCase()).filter(Boolean))];
  if (!countries.length) countries = [String(body.country || C.DEFAULT_COUNTRY).toUpperCase()];
  if (!byMarket) countries = [countries[0]];        // TikTok tìm kiếm / Reels: thị trường theo tài khoản + IP, quét 1 lần
  const maxItems = Math.max(10, Math.min(+body.max_items || 200, 1000));
  let queued = 0;
  for (const kw of kws.slice(0, 50)) for (const country of countries.slice(0, 20)) {
    if (body.save) await db.addSocialWatch(body.platform, kw, byMarket ? country : "");
    queued += jobs.submit("social", jobs.socialTitle(body.platform, kw, country),
      {platform: body.platform, keyword: kw, country, max_items: maxItems, period: +body.period || 7});
  }
  return {ok: true, queued};
});

// Hashtag xu hướng theo thị trường; đánh dấu hashtag khớp từ khoá bạn đang theo dõi.
route("GET", "/api/trends", async ({q}) => {
  let rows = await db.listTrends();
  const present = [...new Set(rows.map(r => r.market))].sort();
  const words = new Set([...(await db.listSocialWatch()).filter(w => w.keyword).map(w => w.keyword.toLowerCase().replace(/^#+/, "")),
    ...(await db.listWatchKeywords()).map(w => w.keyword.toLowerCase())]);
  const tokens = new Set([...words].flatMap(w => w.replace(/#/g, " ").split(/\s+/)).filter(t => t.length > 2));
  if (str(q, "market")) rows = rows.filter(r => r.market === q.get("market"));
  if (str(q, "q")) { const ql = q.get("q").toLowerCase().replace(/^#+/, ""); rows = rows.filter(r => r.name.includes(ql)); }
  for (const r of rows) {
    r.match = [...tokens].filter(t => r.name.includes(t)).sort();
    r.move = r.prev_rank && r.rank ? r.prev_rank - r.rank : null;
  }
  return {items: rows, markets: present, names: C.MARKETS};
});

// ---------------- tải ảnh / video (trình tải của Chrome) ----------------

route("GET", "/api/media/{kind}/{key:path}", async ({params, q}) => {
  const type = q.get("type") || "video";
  need(["ad", "video", "social"].includes(params.kind) && ["video", "image"].includes(type), "Not Found", 404);
  const t = await jobs.mediaTarget(params.kind, params.key);
  need(t, "Not Found", 404);
  try {
    return await media.download({url: type === "video" ? t.video : t.image, local: t.local, kind: type, name: t.name});
  } catch (e) { throw new HttpError(502, e.message); }
});

route("POST", "/api/media/batch", async ({body}) => {
  need(["video", "image", "both"].includes(body.kind || "video"), "kind phải là video / image / both");
  const targets = [...(body.cids || []).map(c => ["video", c]), ...(body.vids || []).map(v => ["social", v])].slice(0, C.MEDIA_BATCH_MAX);
  need(targets.length, "Chưa chọn video nào");
  const queued = jobs.submit("media", `Tải ${targets.length} video (${body.kind || "video"})`, {targets, kind: body.kind || "video"});
  return {queued: queued ? 1 : 0, folder: "Tải về/SnakemediaPOD"};
});

route("GET", "/api/viral/{vid:path}", async ({params}) => {
  const r = await db.socialRow(params.vid);
  need(r, "Not Found", 404);
  const v = social.summarize(r, (await db.socialSnapshots(new Set([params.vid])))[params.vid] || []);
  await withThumbs([v], "cover_path", "cover_src");
  return v;
});

// ---------------- chế độ an toàn ----------------

const SAFETY_TIPS = [
  "Nên tạo 1 hồ sơ Chrome riêng (bấm ảnh hồ sơ góc trên Chrome → Thêm), đăng nhập tài khoản Facebook/TikTok phụ đã dùng bình thường một thời gian, rồi cài tiện ích trong hồ sơ đó. Đừng quét bằng tài khoản chính.",
  "Không quét khi đang bật VPN đổi quốc gia liên tục.",
  "Trong lúc quét, để cửa sổ quét hiện trên màn hình (không thu nhỏ, không bị cửa sổ khác che hết) — Chrome ngừng tải trang bị ẩn.",
  "Gặp checkpoint: tự xác minh trên Facebook/TikTok, đợi vài tiếng rồi mới quét tiếp.",
  "Đừng tăng giới hạn quét/ngày quá cao; quét đều mỗi đêm an toàn hơn quét dồn một lúc.",
];

route("GET", "/api/safety", async () => ({platforms: await safety.status(), tips: SAFETY_TIPS}));

route("POST", "/api/safety/resume/{platform}", async ({params}) => {
  need(params.platform in safety.PLATFORMS, "Not Found", 404);
  await safety.resume(params.platform);
  jobs.log(`Đã mở lại quét ${safety.PLATFORMS[params.platform]}`);
  return {ok: true};
});

route("POST", "/api/safety/limits", async ({body}) => {
  try {
    await safety.setLimits(body.platform, +body.min_gap_s, +body.max_per_day);
  } catch (e) {
    if (e instanceof RangeError) throw new HttpError(400, e.message);
    throw e;
  }
  return {ok: true};
});

// ---------------- thông báo Telegram / Chrome ----------------

route("GET", "/api/notify", () => notify.publicSettings());

route("POST", "/api/notify", async ({body}) => {
  await notify.saveSettings({telegram_token: body.telegram_token ?? null, telegram_chat_id: body.telegram_chat_id ?? null,
    desktop: body.desktop ?? null, events: body.events ?? null});
  return notify.publicSettings();
});

route("POST", "/api/notify/find-chat", async () => {
  const s = await notify.settings();
  need(s.telegram_token, "Chưa nhập token bot Telegram");
  let chat;
  try { chat = await notify.findChatId(s.telegram_token); } catch (e) {
    throw new HttpError(400, `Không đọc được tin nhắn của bot: ${e.message}`);
  }
  need(chat, "Chưa thấy tin nhắn nào. Mở Telegram, nhắn /start cho bot của bạn rồi bấm lại.");
  await notify.saveSettings({telegram_chat_id: chat});
  return notify.publicSettings();
});

route("POST", "/api/notify/test", async () => {
  const msgs = [];
  const sent = await notify.send("🐍 SNAKEMEDIA POD: thử thông báo", ["Nếu bạn thấy tin này, thông báo đã chạy."], m => msgs.push(m));
  need(sent.length, msgs.join("; ") || "Chưa bật kênh nào (nhập Telegram hoặc bật thông báo Chrome)");
  return {sent, errors: msgs};
});

route("GET", "/api/diag", () => diag.listBundles());

route("GET", "/api/diag/{name}/download", async ({params}) => {
  const data = await diag.zipBundle(params.name);
  need(data !== null, "Not Found", 404);
  return {filename: `${params.name}.zip`, base64: data};
});

// Mở Facebook / TikTok trong 1 tab để bạn tự đăng nhập / xác minh checkpoint.
route("POST", "/api/login/{site}", async ({params}) => {
  const url = {facebook: `${URLS.FB}/`, tiktok: `${URLS.TIKTOK}/login`, pinterest: `${URLS.PINTEREST}/login/`}[params.site];
  need(url, "Not Found", 404);
  await chrome.tabs.create({url});
  return {ok: true};
});

// ---------------- từ khoá tự quét + lịch ----------------

route("GET", "/api/keywords", () => db.listWatchKeywords());

route("DELETE", "/api/keywords/{keyword}", async ({params}) => {
  await db.removeWatchKeyword(params.keyword);
  return {ok: true};
});

async function autoscan() {
  return {...(await jobs.autoSettings()), keywords: (await db.listWatchKeywords()).length, follows: (await db.listFollows()).length};
}

route("GET", "/api/autoscan", autoscan);

route("POST", "/api/autoscan", async ({body}) => {
  const hour = +body.hour;
  need(Number.isInteger(hour) && hour >= 0 && hour <= 23, "Giờ phải từ 0 đến 23");
  const stores = body.stores === null || body.stores === undefined ? null : +body.stores;
  need(stores === null || (Number.isInteger(stores) && stores >= 0 && stores <= 200), "Số shop soi mỗi đêm: 0–200");
  const cur = await jobs.autoSettings();
  await db.setSetting("auto", {...cur, enabled: !!body.enabled, hour, stores: stores === null ? cur.stores : stores});
  return autoscan();
});

route("POST", "/api/autoscan/run", async () => ({queued: await jobs.queueAllWatched("Quét tất cả (bấm tay)")}));

// ---------------- theo dõi page / shop + kho shop ----------------

function activity(ads, t) {
  const active = ads.filter(a => a.is_active);
  const starts = ads.map(a => a.start_ts).filter(Boolean);
  return {
    ads: ads.length,
    active: active.length,
    new_24h: ads.filter(a => a.start_ts && t - a.start_ts <= DAY).length,
    new_7d: ads.filter(a => a.start_ts && t - a.start_ts <= 7 * DAY).length,
    off_2d: ads.filter(a => !a.is_active && a.end_ts && t - a.end_ts <= 2 * DAY).length,
    first_ts: starts.length ? Math.min(...starts) : null,
  };
}

route("GET", "/api/follows", async () => {
  const t = db.now(), out = [];
  for (const f of await db.listFollows())
    out.push({...f, ...activity(await db.adsWhere(f.kind === "page" ? "page_id" : "domain", f.key), t)});
  return out;
});

route("POST", "/api/follows", async ({body}) => {
  const key = String(body.key || "").trim();
  need(["page", "shop"].includes(body.kind) && key, "kind phải là 'page' hoặc 'shop'");
  await db.addFollow(body.kind, key, body.name ?? null);
  return {ok: true};
});

route("DELETE", "/api/follows/{kind}/{key}", async ({params}) => {
  await db.removeFollow(params.kind, params.key);
  return {ok: true};
});

route("POST", "/api/follows/{kind}/{key}/scan", async ({params, q}) => {
  const f = (await db.listFollows()).find(x => x.kind === params.kind && x.key === params.key);
  need(f, "Not Found", 404);
  jobs.submit("follow", `Theo dõi ${params.kind} ${f.name || params.key}`,
    {kind: params.kind, key: params.key, country: q.get("country") || C.DEFAULT_COUNTRY});
  return {ok: true};
});

route("GET", "/api/shops", async () => {
  const followed = new Set((await db.listFollows()).filter(f => f.kind === "shop").map(f => f.key));
  const vids = await db.listVideos();
  return (await db.shopRows()).map(r => {
    const mine = vids.filter(v => v.shops.includes(r.domain));
    return {...r, followed: followed.has(r.domain), videos: mine.length,
      hot: mine.filter(v => ["sap_win", "win"].includes(v.label)).length, pod: mine.some(v => v.is_pod)};
  });
});

// ---------------- việc đang chạy ----------------

route("POST", "/api/recompute", () => { jobs.submit("recompute", "Chấm lại", {}); return {ok: true}; });
// ---------------- Kết nối Shopify + Clone ----------------

route("GET", "/api/shopify", () => shopify.status());

const shopifyCall = async fn => {
  try { return await fn(); } catch (e) {
    if (e instanceof shopify.ShopifyError) throw new HttpError(400, e.message);
    throw e;
  }
};

route("POST", "/api/shopify", ({body}) => shopifyCall(() => shopify.connect(body.shop, body.client_id, body.client_secret)));

route("DELETE", "/api/shopify", async () => { await shopify.disconnect(); return {ok: true}; });

// Trang bán để clone: ưu tiên trang Shopify có nhiều QC nhất, rồi link chính của video
function cloneUrl(v) {
  const pages = v.sell_pages || [];
  const best = pages.find(p => p.platform === "shopify") || pages[0];
  return (best && best.url) || v.main_link || null;
}

route("POST", "/api/shopify/clone", async ({body}) => {
  let url = body.url || null;
  if (body.cid) {
    const v = await db.getVideo(body.cid);
    need(v, "Không tìm thấy video", 404);
    url = url || cloneUrl(v);
  }
  need(url && /^https?:\/\//.test(url), "Video này chưa có trang bán để clone");
  const rec = await shopifyCall(() => shopify.clone(url, body.cid || null));
  jobs.log(`Đã clone '${rec.title.slice(0, 60)}' vào store ${rec.shop} (bản nháp)`);
  return rec;
});

// ---------------- Gợi ý từ khoá: Pinterest / Google Trends / Tự đào ----------------

route("GET", "/api/kwtrends", async ({q}) => {
  const source = q.get("source") || "pinterest";
  need(source in kwtrends.SOURCES, "Not Found", 404);
  const market = (q.get("market") || C.DEFAULT_COUNTRY).toUpperCase();
  const data = (await db.getSetting("kwtrends", {}))[source] || {};
  const cur = data[market] || {ts: null, items: []};
  const known = await jobs.knownKeywords();
  const items = cur.items.map(it => ({...it, scanned: known.has(it.term)}));
  const groups = new Map();
  for (const it of items) {
    const name = it.group || "";
    const g = groups.get(name) || {name, terms: 0, unscanned: 0, best: null};
    g.terms++;
    g.unscanned += it.scanned ? 0 : 1;
    g.best = Math.max(g.best || it.score || 0, it.score || 0);
    groups.set(name, g);
  }
  return {source, market, ts: cur.ts, items, markets: Object.keys(data).sort(),
    groups: [...groups.values()].sort((a, b) => (b.best || 0) - (a.best || 0)),
    unscanned: items.filter(it => !it.scanned).length, sources: kwtrends.SOURCES};
});

route("POST", "/api/kwtrends/refresh", async ({body}) => {
  need(body.source in kwtrends.SOURCES, "Nguồn không hợp lệ");
  let countries = [...new Set((body.countries || ["US"]).map(c => String(c).trim().toUpperCase()).filter(Boolean))].slice(0, 13);
  if (!countries.length) countries = [C.DEFAULT_COUNTRY];
  let queued = 0;
  for (const c of countries) queued += jobs.submit("kwtrend", `Xu hướng ${kwtrends.SOURCES[body.source]} ${c}`, {source: body.source, geo: c});
  return {queued};
});

route("POST", "/api/stop", () => { jobs.stopCurrent(); return {ok: true}; });
route("GET", "/api/jobs", () => jobs.status());
route("GET", "/api/scans", () => db.listScans());

// ---------------- riêng cho tiện ích ----------------

route("GET", "/api/passive", async () => ({enabled: await jobs.passiveEnabled()}));
route("POST", "/api/passive", async ({body}) => {
  await db.setSetting("passive", {enabled: !!body.enabled});
  return {enabled: !!body.enabled};
});

route("POST", "/api/demo", async () => {
  try { return {ads: await demo.load()}; } catch (e) { throw new HttpError(400, e.message); }
});

route("GET", "/api/info", async () => ({
  version: chrome.runtime.getManifest().version, demo: await db.getSetting("demo", false),
  has_data: (await db.count("ads")) + (await db.count("social_videos")) > 0,
}));
