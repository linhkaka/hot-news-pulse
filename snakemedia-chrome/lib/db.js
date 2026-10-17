// Lưu trữ trong IndexedDB của tiện ích (giống các bảng SQLite của snakemedia-pod/snakepod/db.py).
// Dữ liệu nằm trong hồ sơ Chrome của bạn; gỡ tiện ích là mất dữ liệu.

const NAME = "snakepod";
const VERSION = 1;
let _db = null;

const STORES = {
  ads: {keyPath: "ad_id", indexes: ["page_id", "domain"]},
  landings: {keyPath: "url"},
  videos: {keyPath: "cid"},
  follows: {keyPath: ["kind", "key"]},
  watch_keywords: {keyPath: "keyword"},
  settings: {keyPath: "key"},
  social_videos: {keyPath: "vid", indexes: ["platform"]},
  social_snapshots: {autoIncrement: true, keyPath: "id", indexes: ["vid"]},
  social_watch: {keyPath: ["platform", "keyword"]},
  rate_events: {autoIncrement: true, keyPath: "id", indexes: ["platform"]},
  notified: {keyPath: ["kind", "key"]},
  scans: {autoIncrement: true, keyPath: "id"},
  thumbs: {keyPath: "name"},
  diag: {keyPath: "name"},
};

export const now = () => Math.floor(Date.now() / 1000);

export function open() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const r = indexedDB.open(NAME, VERSION);
    r.onupgradeneeded = () => {
      const db = r.result;
      for (const [name, s] of Object.entries(STORES)) {
        if (db.objectStoreNames.contains(name)) continue;
        const st = db.createObjectStore(name, {keyPath: s.keyPath, autoIncrement: !!s.autoIncrement});
        for (const ix of s.indexes || []) st.createIndex(ix, ix);
      }
    };
    r.onsuccess = () => { _db = r.result; _db.onversionchange = () => { _db.close(); _db = null; }; resolve(_db); };
    r.onerror = () => reject(r.error);
  });
}

const req = r => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });

// Chạy fn(stores) trong 1 giao dịch; trả về giá trị fn trả về khi giao dịch xong.
async function tx(names, mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(names, mode);
    const stores = Object.fromEntries([].concat(names).map(n => [n, t.objectStore(n)]));
    let out;
    Promise.resolve(fn(stores)).then(v => { out = v; }, e => { reject(e); try { t.abort(); } catch {} });
    t.oncomplete = () => resolve(out);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error("Giao dịch bị huỷ"));
  });
}

export const getAll = (store, index, key) =>
  tx(store, "readonly", s => req(index ? s[store].index(index).getAll(key) : s[store].getAll()));
export const get = (store, key) => tx(store, "readonly", s => req(s[store].get(key)));
export const put = (store, obj) => tx(store, "readwrite", s => req(s[store].put(obj)));
export const del = (store, key) => tx(store, "readwrite", s => req(s[store].delete(key)));
export const clear = store => tx(store, "readwrite", s => req(s[store].clear()));
export const count = store => tx(store, "readonly", s => req(s[store].count()));
export async function putMany(store, items) {
  if (!items.length) return;
  await tx(store, "readwrite", s => { for (const it of items) s[store].put(it); });
}

export async function wipeAll() {
  const names = Object.keys(STORES);
  await tx(names, "readwrite", s => { for (const n of names) s[n].clear(); });
}

const coalesce = (...v) => v.find(x => x !== null && x !== undefined) ?? null;

// ---- quảng cáo ----

const AD_FIELDS = ["ad_id", "collation_id", "collation_count", "page_id", "page_name", "start_ts", "end_ts", "is_active",
  "title", "body", "link_url", "domain", "thumb_url", "video_url"];

export async function upsertAds(ads, keyword = null) {
  // Lưu QC. Giữ nguyên ảnh/hash đã tải, cập nhật trạng thái chạy mới nhất.
  const t = now();
  await tx("ads", "readwrite", async s => {
    for (const a of ads) {
      const old = await req(s.ads.get(a.ad_id));
      if (!old) {
        const row = {thumb_path: null, dhash: null, keyword, first_seen: t, last_seen: t};
        for (const f of AD_FIELDS) row[f] = a[f] ?? null;
        s.ads.put(row);
      } else {
        const st = [old.start_ts, a.start_ts].filter(x => x !== null && x !== undefined);
        s.ads.put({...old, collation_id: a.collation_id ?? null, collation_count: a.collation_count ?? null,
          end_ts: a.end_ts ?? null, is_active: a.is_active ?? null, start_ts: st.length ? Math.min(...st) : null,
          thumb_url: coalesce(a.thumb_url, old.thumb_url), video_url: coalesce(a.video_url, old.video_url),
          keyword: coalesce(old.keyword, keyword), last_seen: t});
      }
    }
  });
}

export const allAds = () => getAll("ads");

export async function adsMissingThumbs() {
  return (await allAds()).filter(a => a.dhash == null && a.thumb_url != null).map(a => ({ad_id: a.ad_id, thumb_url: a.thumb_url}));
}

export async function setThumb(adId, path, dhash) {
  await tx("ads", "readwrite", async s => {
    const a = await req(s.ads.get(adId));
    if (a) s.ads.put({...a, thumb_path: path, dhash});
  });
}

export async function uncheckedLandingUrls(maxAgeS = 3 * 86400) {
  const cutoff = now() - maxAgeS;
  const [ads, lands] = await Promise.all([allAds(), landingsByUrl()]);
  const out = new Set();
  for (const a of ads) {
    if (a.link_url == null) continue;
    const l = lands[a.link_url];
    if (!l || l.checked_ts < cutoff) out.add(a.link_url);
  }
  return [...out];
}

export async function saveLanding(info) {
  await put("landings", {date_source: null, pod_markers: null, ...info});
}

export async function landingsByUrl() {
  return Object.fromEntries((await getAll("landings")).map(l => [l.url, l]));
}

export async function replaceVideos(videos) {
  await tx("videos", "readwrite", s => {
    s.videos.clear();
    videos.forEach((v, i) => s.videos.put({...v, _rank: i}));   // _rank: giữ thứ tự khi cùng số QC/ngày
  });
}

export async function listVideos(label = null) {
  const items = (await getAll("videos")).filter(v => !label || v.label === label);
  return items.sort((a, b) => (b.ads_per_day - a.ads_per_day) || (a._rank - b._rank));
}

export const getVideo = cid => get("videos", cid);

export async function labelCounts() {
  const out = {};
  for (const v of await getAll("videos")) out[v.label] = (out[v.label] || 0) + 1;
  return out;
}

// ---- lượt quét ----

export async function startScan(kind, target) {
  return put("scans", {kind, target, status: "dang chay", n_ads: 0, started_ts: now(), finished_ts: null, error: null});
}

export async function finishScan(id, status, nAds = 0, error = null) {
  await tx("scans", "readwrite", async s => {
    const r = await req(s.scans.get(id));
    if (r) s.scans.put({...r, status, n_ads: nAds, finished_ts: now(), error});
  });
}

export async function listScans(limit = 50) {
  return (await getAll("scans")).sort((a, b) => b.id - a.id).slice(0, limit);
}

// ---- theo dõi page / shop ----

export async function addFollow(kind, key, name = null) {
  if (await get("follows", [kind, key])) return;
  await put("follows", {kind, key, name, added_ts: now(), last_scan_ts: null});
}
export const removeFollow = (kind, key) => del("follows", [kind, key]);
export async function listFollows() {
  return (await getAll("follows")).sort((a, b) => b.added_ts - a.added_ts);
}
export async function touchFollow(kind, key) {
  const f = await get("follows", [kind, key]);
  if (f) await put("follows", {...f, last_scan_ts: now()});
}

// ---- từ khoá tự quét ----

export async function addWatchKeyword(keyword, country) {
  const old = await get("watch_keywords", keyword);
  await put("watch_keywords", {keyword, country, added_ts: now(), last_scan_ts: old ? old.last_scan_ts : null});
}
export const removeWatchKeyword = keyword => del("watch_keywords", keyword);
export async function listWatchKeywords() {
  return (await getAll("watch_keywords")).sort((a, b) => (a.keyword < b.keyword ? -1 : a.keyword > b.keyword ? 1 : 0));
}
export async function touchWatchKeyword(keyword) {
  const k = await get("watch_keywords", keyword);
  if (k) await put("watch_keywords", {...k, last_scan_ts: now()});
}

// ---- cài đặt ----

export async function getSetting(key, dflt = null) {
  const r = await get("settings", key);
  return r ? structuredClone(r.value) : dflt;
}
export const setSetting = (key, value) => put("settings", {key, value});

// ---- thống kê theo shop / page ----

export async function adsWhere(column, value) {
  if (!["page_id", "domain"].includes(column)) throw new Error("cột không hợp lệ");
  return getAll("ads", column, value);
}

export async function shopRows() {
  const [ads, lands] = await Promise.all([allAds(), landingsByUrl()]);
  const by = new Map();
  const maxStr = (a, b) => (a == null ? b : b == null ? a : (b > a ? b : a));
  for (const a of ads) {
    if (a.domain == null) continue;
    let r = by.get(a.domain);
    if (!r) by.set(a.domain, r = {domain: a.domain, ads: 0, active: 0, first_ts: null, last_ts: null, _pages: new Set(),
      platform: null, pod_markers: null});
    r.ads += 1;
    r.active += a.is_active || 0;
    if (a.start_ts != null) {
      r.first_ts = r.first_ts == null ? a.start_ts : Math.min(r.first_ts, a.start_ts);
      r.last_ts = r.last_ts == null ? a.start_ts : Math.max(r.last_ts, a.start_ts);
    }
    if (a.page_id != null) r._pages.add(a.page_id);
    const l = lands[a.link_url];
    if (l) { r.platform = maxStr(r.platform, l.platform); r.pod_markers = maxStr(r.pod_markers, l.pod_markers); }
  }
  const out = [...by.values()].map(({_pages, ...r}) => ({...r, pages: _pages.size}));
  return out.sort((a, b) => (b.active - a.active) || (b.ads - a.ads));
}

// ---- video viral (TikTok / Facebook Reels) ----

const SOCIAL_FIELDS = ["vid", "platform", "item_id", "url", "author", "caption", "cover_url", "video_url", "views", "likes",
  "comments", "shares", "saves", "created_ts", "duration", "extra"];

export async function upsertSocial(items, keyword = null, t = null, minGapS = 0) {
  // Lưu video + 1 bản chụp số liệu (để tính tốc độ tăng thật giữa các lần quét).
  // minGapS > 0: bỏ qua bản chụp nếu video vừa được chụp trong minGapS giây (tự lưu khi lướt chụp liên tục).
  t = t || now();
  await tx(["social_videos", "social_snapshots"], "readwrite", async s => {
    for (const it of items) {
      const old = await req(s.social_videos.get(it.vid));
      if (!old) {
        const row = {cover_path: null, keyword, first_seen: t, last_seen: t};
        for (const f of SOCIAL_FIELDS) row[f] = it[f] ?? null;
        s.social_videos.put(row);
      } else {
        const upd = {...old, last_seen: t, created_ts: coalesce(old.created_ts, it.created_ts), keyword: coalesce(old.keyword, keyword)};
        for (const f of ["url", "caption", "cover_url", "video_url", "views", "likes", "comments", "shares", "saves", "extra"])
          upd[f] = coalesce(it[f], old[f]);
        s.social_videos.put(upd);
      }
      if (minGapS) {
        const prev = await req(s.social_snapshots.index("vid").getAll(it.vid));
        if (prev.some(r => t - r.ts < minGapS)) continue;
      }
      s.social_snapshots.put({vid: it.vid, ts: t, views: it.views ?? null, likes: it.likes ?? null,
        comments: it.comments ?? null, shares: it.shares ?? null});
    }
  });
}

export const socialRows = (platform = null) => platform ? getAll("social_videos", "platform", platform) : getAll("social_videos");
export const socialRow = vid => get("social_videos", vid);

// {vid: [[ts, views, likes, comments, shares], ...]} theo thời gian tăng dần
export async function socialSnapshots(vids = null) {
  const out = {};
  const rows = (await getAll("social_snapshots")).sort((a, b) => (a.ts - b.ts) || (a.id - b.id));
  for (const r of rows) {
    if (vids && !vids.has(r.vid)) continue;
    (out[r.vid] ||= []).push([r.ts, r.views, r.likes, r.comments, r.shares]);
  }
  return out;
}

export async function socialMissingCovers() {
  return (await socialRows()).filter(v => v.cover_path == null && v.cover_url != null)
    .map(v => ({vid: v.vid, platform: v.platform, cover_url: v.cover_url}));
}

export async function setSocialCover(vid, path) {
  await tx("social_videos", "readwrite", async s => {
    const v = await req(s.social_videos.get(vid));
    if (v) s.social_videos.put({...v, cover_path: path});
  });
}

export async function addSocialWatch(platform, keyword, country) {
  if (await get("social_watch", [platform, keyword])) return;
  await put("social_watch", {platform, keyword, country, added_ts: now(), last_scan_ts: null});
}
export const removeSocialWatch = (platform, keyword) => del("social_watch", [platform, keyword]);
export async function listSocialWatch() {
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  return (await getAll("social_watch")).sort((a, b) => cmp(a.platform, b.platform) || cmp(a.keyword, b.keyword));
}
export async function touchSocialWatch(platform, keyword) {
  const w = await get("social_watch", [platform, keyword]);
  if (w) await put("social_watch", {...w, last_scan_ts: now()});
}

// ---- chế độ an toàn: nhật ký lượt quét theo nền tảng ----

export const addRateEvent = (platform, ts = null) => put("rate_events", {platform, ts: ts || now()});
export async function countRateEvents(platform, since) {
  return (await getAll("rate_events", "platform", platform)).filter(r => r.ts >= since).length;
}
export async function lastRateEvent(platform) {
  const rows = await getAll("rate_events", "platform", platform);
  return rows.length ? Math.max(...rows.map(r => r.ts)) : null;
}

// ---- thông báo: nhớ cái đã báo ----

export async function unseenNotified(kind, keys) {
  if (!keys.length) return [];
  const seen = new Set((await getAll("notified")).filter(r => r.kind === kind).map(r => r.key));
  return keys.filter(k => !seen.has(k));
}

export async function markNotified(kind, keys) {
  const t = now();
  await tx("notified", "readwrite", async s => {
    for (const k of keys) if (!(await req(s.notified.get([kind, k])))) s.notified.put({kind, key: k, ts: t});
  });
}

export async function adsFirstSeenSince(column, value, since) {
  return (await adsWhere(column, value)).filter(a => a.first_seen >= since).length;
}

// ---- ảnh thumbnail / ảnh bìa (lưu dạng data URL) ----

export const saveThumb = (name, data) => put("thumbs", {name, data});
export async function thumbData(names) {
  const want = [...new Set(names.filter(Boolean))];
  if (!want.length) return {};
  const rows = await tx("thumbs", "readonly", s => Promise.all(want.map(n => req(s.thumbs.get(n)))));
  return Object.fromEntries(rows.filter(Boolean).map(r => [r.name, r.data]));
}
