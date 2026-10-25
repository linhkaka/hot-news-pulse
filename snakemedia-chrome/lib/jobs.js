// Hàng đợi việc chạy nền (quét, đào sâu) + nhật ký hiển thị trên giao diện (giống snakepod/jobs.py).
//
// Mỗi việc là dữ liệu {kind, title, args} và được lưu lại, nên Chrome tắt giữa chừng thì lần mở sau
// các việc còn chờ vẫn chạy tiếp.
import {C, URLS} from "./config.js";
import * as db from "./db.js";
import * as analyze from "./analyze.js";
import * as landing from "./landing.js";
import * as notify from "./notify.js";
import * as safety from "./safety.js";
import * as scanner from "./scanner.js";
import * as social from "./social.js";
import {pyRound} from "./social.js";
import * as demo from "./demo.js";
import {fetchImage} from "./imagehash.js";
import * as media from "./media.js";
import * as kwtrends from "./kwtrends.js";
import {parseJsonText} from "./fbparser.js";

const LOG = [];
const state = {current: null, pending: [], stop: false, running: false, kind: null, started: null, count: 0, job: null};
// Phiên quét: các việc đã xong kể từ lúc hàng đợi rảnh -> bảng tiến độ "đang quét 9 / 25"
const SESSION = [];
const EST_JOB_S = 120;          // ước lượng 1 việc khi chưa có việc nào xong (giây)
const hasStorage = () => globalThis.chrome && chrome.storage && chrome.storage.local;

function persist() {
  // Lưu cả việc đang chạy (không chỉ tên) để Chrome tắt giữa chừng thì lần mở sau chạy lại việc đó
  if (hasStorage()) chrome.storage.local.set({jobs: {pending: state.pending, current: state.current, job: state.job, log: LOG}}).catch(() => {});
}

export function log(msg) {
  LOG.push({ts: db.now(), msg});
  if (LOG.length > 300) LOG.splice(0, LOG.length - 300);
  console.log(new Date().toLocaleTimeString(), msg);
  persist();
}

// Số QC / video đã đọc của việc đang chạy (bộ quét gọi mỗi lần đọc thêm)
export function setProgress(n) { state.count = Math.trunc(n); }

// Tiến độ phiên quét: việc xong (kèm số QC, thời gian), việc đang chạy, tốc độ QC/phút, thời gian còn lại.
export function progress(t = Date.now() / 1000) {
  const done = SESSION.slice();
  const cur = state.current ? {title: state.current, kind: state.kind, count: state.count, secs: Math.trunc(t - (state.started || t))} : null;
  const items = done.reduce((a, d) => a + d.n, 0) + (cur ? cur.count : 0);
  const secs = done.reduce((a, d) => a + d.secs, 0) + (cur ? cur.secs : 0);
  const avg = done.length ? done.reduce((a, d) => a + d.secs, 0) / done.length : EST_JOB_S;
  const left = state.pending.length * avg + (cur ? Math.max(0, avg - cur.secs) : 0);
  return {done: done.slice(-30), n_done: done.length, current: cur, pending: state.pending.map(j => j.title),
    total: done.length + (cur ? 1 : 0) + state.pending.length, items,
    rate: secs >= 30 ? pyRound(items * 60 / secs) : null, eta_s: cur || state.pending.length ? Math.trunc(left) : 0};
}

// Chỉ dùng cho bài kiểm thử
export const _test = {state, SESSION};

export async function status() {
  return {current: state.current, pending: state.pending.map(j => j.title), log: LOG.slice(-80), blocked: await safety.blocked(),
    progress: progress()};
}

// Xếp việc vào hàng đợi. Bỏ qua nếu việc trùng tên đang chờ/đang chạy.
export function submit(kind, title, args = {}) {
  if (state.pending.some(j => j.title === title) || state.current === title) return false;
  if (!state.current && !state.pending.length) SESSION.length = 0;   // hàng đợi đang rảnh -> bắt đầu phiên mới
  state.pending.push({kind, title, args});
  persist();
  kick();
  return true;
}

export function stopCurrent() { state.stop = true; }
export const shouldStop = () => state.stop;
export const isBusy = () => state.running;

// Khởi động lại phần nền (Chrome mở lại / tiện ích cập nhật): lấy lại nhật ký và các việc còn chờ.
export async function restore() {
  if (!hasStorage()) return;
  const {jobs} = await chrome.storage.local.get("jobs");
  if (!jobs) return;
  LOG.splice(0, LOG.length, ...(jobs.log || []));
  await scanner.closeLeftoverWindows().catch(() => {});
  await db.markInterruptedScans().catch(() => {});
  if (jobs.current) {
    const again = jobs.job && !jobs.job.retried;   // chạy lại 1 lần; gián đoạn lần 2 thì bỏ (tránh lặp mãi)
    log(`Việc '${jobs.current}' bị gián đoạn (Chrome tắt hoặc tiện ích khởi động lại)` + (again ? " — chạy lại" : ""));
    if (again && !state.pending.some(p => p.title === jobs.job.title)) state.pending.unshift({...jobs.job, retried: true});
  }
  for (const j of jobs.pending || []) if (!state.pending.some(p => p.title === j.title)) state.pending.push(j);
  persist();
  kick();
}

function kick() {
  if (state.running) return;
  state.running = true;
  runLoop().catch(e => log(`Lỗi hàng đợi: ${e && e.message || e}`)).finally(() => {
    state.running = false;
    if (state.pending.length) kick();
  });
}

// Ghi kết quả vào lịch sử quét; lỗi ghi (bộ nhớ đầy...) không được làm dừng hàng đợi
async function finish(scanId, st, n, err = null) {
  if (scanId == null) return;
  try { await db.finishScan(scanId, st, n, err); } catch (e) { console.error(e); }
}

async function runLoop() {
  while (state.pending.length) {
    const job = state.pending.shift();
    Object.assign(state, {current: job.title, kind: job.kind, stop: false, started: Date.now() / 1000, count: 0, job});
    persist();
    let n = 0, st = "xong", scanId = null;
    // Giữ phần nền của tiện ích thức trong lúc chạy việc dài (Chrome tự tắt phần nền rảnh sau 30 giây)
    const keepAlive = setInterval(() => chrome.runtime.getPlatformInfo().catch(() => {}), 20000);
    try {
      scanId = await db.startScan(job.kind, job.title);
      n = (await JOBS[job.kind](job.args)) || 0;
      st = state.stop ? "da dung" : "xong";
      await finish(scanId, st, n);
      log(`Xong: ${job.title}`);
    } catch (e) {
      n = 0;
      if (e instanceof safety.Skipped) {
        st = "bo qua";
        await finish(scanId, "bo qua", 0, String(e.message).slice(0, 500));
        log(`Bỏ qua '${job.title}': ${e.message}`);
      } else if (e instanceof safety.CheckpointError) {
        st = "checkpoint";
        await safety.block(e.platform, e.reason, e.url).catch(() => {});
        await finish(scanId, "checkpoint", 0, e.reason);
        log(`⚠ ${e.reason}. ĐÃ TẠM DỪNG mọi lượt quét ${safety.PLATFORMS[e.platform]}. ` +
          "Hãy tự xác minh trên Facebook/TikTok rồi bấm 'Đã xử lý, quét tiếp'.");
        await notify.send(`⚠ SNAKEMEDIA POD: ${e.reason}`, ["Đã tạm dừng quét để bảo vệ tài khoản."], log).catch(() => {});
      } else {
        st = "loi";
        await finish(scanId, "loi", 0, String(e && e.message || e).slice(0, 500));
        log(`Lỗi khi chạy '${job.title}': ${e && e.message || e}`);
      }
    } finally {
      clearInterval(keepAlive);
      SESSION.push({title: job.title, kind: job.kind, n: Math.trunc(n), status: st, secs: Math.trunc(Date.now() / 1000 - state.started), ts: db.now()});
      if (SESSION.length > 200) SESSION.splice(0, SESSION.length - 200);
      Object.assign(state, {current: null, kind: null, count: 0, job: null});
      persist();
    }
  }
}

// ---- các bước xử lý sau khi có QC ----

// Chạy work(item) cho nhiều item cùng lúc (HTTP_WORKERS luồng), báo tiến độ, dừng được giữa chừng.
async function parallel(items, work, noun) {
  let next = 0, done = 0;
  const worker = async () => {
    while (next < items.length && !state.stop) {
      const it = items[next++];
      try { await work(it); } catch (e) { log(`  bỏ qua 1 ${noun}: ${e && e.message || e}`); }
      if (++done % 50 === 0) log(`  ... ${done}/${items.length} ${noun}`);
    }
  };
  await Promise.all(Array.from({length: Math.min(C.HTTP_WORKERS, items.length)}, worker));
}

export async function fetchThumbs() {
  const todo = await db.adsMissingThumbs();
  if (!todo.length) return;
  log(`Tải ${todo.length} ảnh thumbnail để nhận diện video trùng`);
  await parallel(todo, async a => {
    const [h, small] = await fetchImage(a.thumb_url);
    const name = `${a.ad_id}.jpg`;
    await db.saveThumb(name, small);
    await db.setThumb(a.ad_id, name, h);
  }, "ảnh");
}

export async function checkLandings() {
  const urls = await db.uncheckedLandingUrls();
  if (!urls.length) return;
  log(`Đọc tuổi ${urls.length} trang bán`);
  // Mỗi shop tối đa 2 yêu cầu cùng lúc để không làm phiền / bị shop chặn
  const slots = new Map();
  const host = u => { try { return new URL(u).host; } catch { return u; } };
  const acquire = async h => {
    let s = slots.get(h);
    if (!s) slots.set(h, s = {n: 0, q: []});
    while (s.n >= 2) await new Promise(r => s.q.push(r));
    s.n++;
  };
  const release = h => { const s = slots.get(h); s.n--; const nx = s.q.shift(); if (nx) nx(); };
  await parallel(urls, async u => {
    const h = host(u);
    await acquire(h);
    try { await db.saveLanding(await landing.check(u)); } finally { release(h); }
  }, "trang bán");
}

export async function recompute() {
  const videos = analyze.buildVideos(await db.allAds(), await db.landingsByUrl());
  await db.replaceVideos(videos);
  await db.rekey(videos);
  await db.recordHistory(videos, ymd(new Date()));
  log(`Đã chấm lại ${videos.length} video`);
  await notify.checkVideos(videos, log);
}

async function processAfterScan() {
  await fetchThumbs();
  await checkLandings();
  await recompute();
}

async function fetchSocialCovers() {
  const todo = await db.socialMissingCovers();
  if (!todo.length) return;
  log(`Tải ${todo.length} ảnh bìa video`);
  await parallel(todo, async v => {
    const [, small] = await fetchImage(v.cover_url);
    const name = "s_" + v.vid.replace(/[^A-Za-z0-9]/g, "_") + ".jpg";
    await db.saveThumb(name, small);
    await db.setSocialCover(v.vid, name);
  }, "ảnh bìa");
}

async function notifySocial(platform, vids) {
  const snaps = await db.socialSnapshots(vids);
  const rows = (await db.socialRows(platform)).filter(r => vids.has(r.vid));
  await notify.checkSocial(rows.map(r => social.summarize(r, snaps[r.vid] || [])), log);
}

const JOBS = {
  async keyword({keyword, country, max_ads}) {
    await demo.clearIfDemo(log);
    log(`Quét từ khoá '${keyword}' (${country})`);
    await safety.beforeScan("facebook", log, shouldStop);
    const ads = await scanner.scanKeyword(keyword, country, max_ads, log, shouldStop, setProgress);
    log(`Đọc được ${ads.length} QC`);
    await db.upsertAds(ads, keyword);
    await db.touchWatchKeyword(keyword);
    await processAfterScan();
    return ads.length;
  },

  // Quét lại 1 page (mọi QC video của page) hoặc 1 shop (tìm domain trong thư viện QC).
  async follow({kind, key, country}) {
    await demo.clearIfDemo(log);
    await safety.beforeScan("facebook", log, shouldStop);
    const started = db.now();
    let ads;
    if (kind === "page") {
      ads = await scanner.scanPages([key], country, C.DIG_MAX_ADS_PER_PAGE, log, shouldStop, setProgress);
    } else {
      log(`Quét shop ${key}`);
      ads = await scanner.scanKeyword(key, country, C.DEFAULT_MAX_ADS, log, shouldStop, setProgress);
      const mine = ads.filter(a => a.domain === key);
      if (mine.length) ads = mine;
    }
    log(`Đọc được ${ads.length} QC`);
    await db.upsertAds(ads);
    await db.touchFollow(kind, key);
    await processAfterScan();
    const fresh = await db.adsFirstSeenSince(kind === "page" ? "page_id" : "domain", key, started);
    if (fresh) {
      const f = (await db.listFollows()).find(x => x.kind === kind && x.key === key);
      const name = (f && f.name) || key;
      log(`${name}: ${fresh} QC mới`);
      await notify.followUpdate(name, fresh, log);
    }
    return ads.length;
  },

  // Quét video viral 1 nguồn theo từ khoá / hashtag (Top Ads, thịnh hành, hashtag xu hướng: từ khoá có thể bỏ trống).
  // Nguồn Creative Center quét đúng thị trường `country`; TikTok tìm kiếm / Reels theo tài khoản + IP của bạn.
  async social({platform, keyword, country, max_items, period = 7}) {
    await demo.clearIfDemo(log);
    const name = social.SOURCES[platform];
    const byMarket = social.MARKET_SOURCES.has(platform);
    log(`Quét ${name} '${keyword || "tất cả"}'` + (byMarket ? ` (${country})` : ""));
    await safety.beforeScan(safety.platformOf(platform), log, shouldStop);
    const items = await scanner.scanSocial(platform, keyword, country, max_items, period, log, shouldStop, setProgress);
    await db.touchSocialWatch(platform, keyword, byMarket ? country : "");
    if (platform === "tiktok_tags") {
      await db.upsertTrends(country, items);
      log(`Đọc được ${items.length} hashtag xu hướng (${country})`);
      return items.length;
    }
    log(`Đọc được ${items.length} video ${name}`);
    await db.upsertSocial(items, keyword || null, null, 0, byMarket ? country : null);
    await fetchSocialCovers();
    await notifySocial(platform, new Set(items.map(it => it.vid)));
    return items.length;
  },

  // Đào sâu: soi toàn bộ QC (cả đã tắt) của các page đang chạy video này để tìm mốc sớm nhất.
  async dig({cid, country}) {
    const v = await db.getVideo(cid);
    if (!v) { log("Không tìm thấy video"); return 0; }
    const pages = v.page_ids.slice(0, C.DIG_MAX_PAGES);
    log(`Đào sâu '${v.title.slice(0, 50)}' qua ${pages.length} page`);
    await safety.beforeScan("facebook", log, shouldStop);
    const ads = await scanner.scanPages(pages, country, C.DIG_MAX_ADS_PER_PAGE, log, shouldStop, setProgress);
    await db.upsertAds(ads);
    await db.markDug(cid);
    await processAfterScan();
    return ads.length;
  },

  // Quét store win: soi 1 shop đang chạy video hot để tìm sản phẩm khác của họ.
  async store({domain, country}) {
    await demo.clearIfDemo(log);
    await safety.beforeScan("facebook", log, shouldStop);
    const known = new Set((await db.allAds()).map(a => a.ad_id));   // QC đã có trước lượt soi
    log(`Soi store ${domain}`);
    let ads = await scanner.scanKeyword(domain, country, C.DEFAULT_MAX_ADS, log, shouldStop, setProgress);
    const mine = ads.filter(a => a.domain === domain);
    if (mine.length) ads = mine;
    await db.upsertAds(ads);
    await processAfterScan();
    const fresh = new Set(ads.map(a => a.ad_id).filter(id => !known.has(id)));
    const newVideos = (await db.listVideos()).filter(v => v.ads.some(a => fresh.has(a.ad_id))).length;
    await db.saveStoreSweep(domain, ads.length, newVideos);
    log(`${domain}: ${ads.length} QC, ${newVideos} video mới`);
    return ads.length;
  },

  async recompute() { await recompute(); return 0; },

  // Gợi ý từ khoá từ xu hướng: Google Trends (RSS) / Pinterest Trends (mở trang trong cửa sổ quét)
  async kwtrend({source, geo}) {
    let items;
    if (source === "google") {
      log(`Lấy tìm kiếm thịnh hành Google Trends (${geo})`);
      const r = await fetch(URLS.GOOGLE_TRENDS_RSS.replace("{geo}", geo), {credentials: "omit"});
      if (!r.ok) throw new Error(`Google Trends trả về mã ${r.status}`);
      items = kwtrends.parseGoogleRss(await r.text());
    } else {
      log(`Mở Pinterest Trends (${geo})`);
      await safety.beforeScan("pinterest", log, shouldStop);
      items = await scanner.scanPinterest(geo, 300, log, shouldStop);
    }
    await kwtrends.save(db, source, geo, items);
    log(`Đọc được ${items.length} từ khoá ${kwtrends.SOURCES[source]} (${geo})`);
    return items.length;
  },

  // Tải hàng loạt ảnh / video (Chrome tự lưu vào Tải về/SnakemediaPOD/<ngày>/)
  async media({targets, kind}) {
    const kinds = kind === "both" ? ["video", "image"] : [kind];
    let ok = 0, fail = 0;
    for (const [k, key] of targets) {
      if (state.stop) break;
      const t = await mediaTarget(k, key);
      if (!t) continue;
      for (const type of kinds) {
        try { await media.download({url: type === "video" ? t.video : t.image, local: t.local, kind: type, name: t.name}); ok++; }
        catch (e) { fail++; log(`  bỏ qua ${t.name} (${type}): ${e.message}`); }
      }
    }
    log(`Đã gửi ${ok} file cho Chrome tải về thư mục Tải về/SnakemediaPOD` + (fail ? `, ${fail} file lỗi` : ""));
    return ok;
  },

  // Tự lưu khi lướt: xử lý các QC / video bạn vừa tự xem trên Facebook / TikTok
  async passive() {
    const vids = new Set(passive.vids);
    passive.vids.clear();
    await processAfterScan();
    await fetchSocialCovers();
    if (vids.size) await notifySocial(null, vids);
    return 0;
  },
};

// ---- tự lưu khi bạn tự lướt Thư viện QC / TikTok (không tính vào giới hạn quét) ----

const passive = {timer: null, vids: new Set()};

export async function passiveEnabled() {
  return (await db.getSetting("passive", {enabled: true})).enabled;
}

function schedulePassive() {
  clearTimeout(passive.timer);
  db.setSetting("passive_dirty", true);
  passive.timer = setTimeout(() => {
    passive.timer = null;
    if (submit("passive", "Lưu QC/video vừa lướt", {})) db.setSetting("passive_dirty", false);
  }, C.PASSIVE_DELAY_S * 1000);
}

// Gọi từ sw.js với dữ liệu 1 tab không do tiện ích quét. Trả về số QC/video đã lưu.
// Tên việc theo dõi; 2 page trùng tên vẫn là 2 việc khác nhau (hàng đợi bỏ việc trùng tên)
export const followTitle = (kind, key, name = null) =>
  name ? `Theo dõi ${kind} ${name}` + (name !== key ? ` (${key})` : "") : `Theo dõi ${kind} ${key}`;

export async function passiveCapture(pageUrl, texts) {
  if (!(await passiveEnabled())) return 0;
  await demo.clearIfDemo(log);           // dữ liệu thật đầu tiên -> xoá dữ liệu mẫu TRƯỚC khi lưu
  const u = String(pageUrl || "");
  let n = 0;
  for (const text of texts) {
    if (u.includes("/ads/library") && text.includes("ad_archive_id")) {
      const ads = parseJsonText(text);
      if (ads.length) { await db.upsertAds(ads, null); n += ads.length; }
      continue;
    }
    let items = [];
    if (u.includes("creativecenter") && text.includes("ad_title")) items = social.parseTopadsText(text);
    else if (text.includes("playCount")) items = social.parseTiktokText(text);
    else if (u.includes("/search/videos") && /play_count|video_view_count/.test(text)) items = social.parseReelsText(text);
    if (items.length) {
      await db.upsertSocial(items, null, null, 600);
      for (const it of items) passive.vids.add(it.vid);
      n += items.length;
    }
  }
  if (n) schedulePassive();
  return n;
}

// ---- tự quét mỗi đêm ----

// Xếp hàng quét lại mọi từ khoá đã lưu và mọi page/shop đang theo dõi.
export async function queueAllWatched(reason) {
  const country = C.DEFAULT_COUNTRY;
  let n = 0;
  for (const w of await db.listWatchKeywords())
    n += submit("keyword", `Quét '${w.keyword}'`, {keyword: w.keyword, country: w.country || country, max_ads: C.DEFAULT_MAX_ADS});
  for (const f of await db.listFollows())
    n += submit("follow", followTitle(f.kind, f.key, f.name), {kind: f.kind, key: f.key, country});
  for (const w of await db.listSocialWatch())
    n += submit("social", socialTitle(w.platform, w.keyword, w.country || country),
      {platform: w.platform, keyword: w.keyword, country: w.country || country, max_items: C.DEFAULT_MAX_ADS});
  const nStores = +(await autoSettings()).stores;
  n += queueSweeps((await storeRows()).filter(r => r.status === "pending").slice(0, nStores).map(r => r.domain), country);
  log(`${reason}: xếp ${n} việc quét`);
  return n;
}

export async function autoSettings() {
  return {enabled: true, hour: C.AUTO_SCAN_HOUR, stores: C.AUTO_SWEEP_STORES, last_date: null, ...(await db.getSetting("auto", {}))};
}

const ymd = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// Tới giờ tự quét (mặc định 1h sáng) và hôm nay chưa quét -> xếp hàng quét. Trả về true nếu đã xếp.
export async function schedulerTick(when = null) {
  const s = await autoSettings();
  when = when || new Date();
  const today = ymd(when);
  if (s.enabled && when.getHours() === +s.hour && s.last_date !== today) {
    await db.setSetting("auto", {...s, last_date: today});
    await queueAllWatched(`Tự quét lúc ${s.hour}h`);
    return true;
  }
  // Dữ liệu lướt còn chưa xử lý (phần nền bị Chrome tắt trước khi kịp làm)
  if (!passive.timer && await db.getSetting("passive_dirty", false)) {
    if (submit("passive", "Lưu QC/video vừa lướt", {})) await db.setSetting("passive_dirty", false);
  }
  return false;
}


// ---- đào sâu hàng loạt ----

// Video Sắp WIN / Tiềm năng chưa đào (hoặc đào đã lâu), nhiều QC/ngày lên trước.
export async function digCandidates() {
  const [dug, mk, vids] = await Promise.all([db.digs(), db.marks(), db.listVideos()]);
  const cut = db.now() - C.DIG_FRESH_DAYS * 86400;
  return vids.filter(v => (v.label === "sap_win" || v.potential) && !(mk[v.cid] && mk[v.cid].has("hidden"))
    && (dug[v.cid] || 0) < cut);
}

// ---- quét store win: soi mọi shop đang chạy video hot để tìm sản phẩm khác của họ ----

const TAB_NAMES = {sap_win: "Sắp WIN", win: "Video Win", scale: "Video scale"};
const TAB_ORDER = ["Theo dõi", "Sắp WIN", "Video Win", "Video scale", "Tiềm năng", "Bò sữa", "Video test"];

// Shop đang chạy video ở các tab Sắp WIN / Win / Scale / Tiềm năng / Bò sữa / Video test / Theo dõi.
export async function storeRows() {
  const [mk, follows, vids, shops, sweeps] = await Promise.all([db.marks(), db.listFollows(), db.listVideos(),
    db.shopRows(), db.storeSweeps()]);
  const tabs = new Map();
  for (const v of vids) {
    const m = mk[v.cid] || new Set();
    if (m.has("hidden")) continue;
    const names = [...(v.label in TAB_NAMES ? [TAB_NAMES[v.label]] : []), ...(v.potential ? ["Tiềm năng"] : []),
      ...(v.cash_cow ? ["Bò sữa"] : []), ...(m.has("test") ? ["Video test"] : [])];
    if (!names.length) continue;
    for (const d of v.shops) {
      if (!tabs.has(d)) tabs.set(d, {tabs: new Set(), videos: 0});
      const t = tabs.get(d);
      names.forEach(n => t.tabs.add(n));
      t.videos += 1;
    }
  }
  for (const f of follows) if (f.kind === "shop") {
    if (!tabs.has(f.key)) tabs.set(f.key, {tabs: new Set(), videos: 0});
    tabs.get(f.key).tabs.add("Theo dõi");
  }
  const byShop = Object.fromEntries(shops.map(r => [r.domain, r]));
  const cut = db.now() - C.STORE_FRESH_DAYS * 86400;
  const out = [...tabs].map(([d, t]) => {
    const r = byShop[d] || {}, sw = sweeps[d] || {};
    return {domain: d, tabs: TAB_ORDER.filter(n => t.tabs.has(n)), hot_videos: t.videos, ads: r.ads || 0, active: r.active || 0,
      pages: r.pages || 0, platform: r.platform ?? null, swept_ts: sw.swept_ts ?? null, ads_found: sw.ads_found ?? null,
      new_videos: sw.new_videos ?? null, status: (sw.swept_ts || 0) >= cut ? "done" : "pending"};
  });
  const rank = r => (r.status !== "pending" ? 1 : 0);
  return out.sort((a, b) => (rank(a) - rank(b)) || (b.ads - a.ads) || (a.domain < b.domain ? -1 : a.domain > b.domain ? 1 : 0));
}

export function queueSweeps(domains, country = C.DEFAULT_COUNTRY) {
  return domains.reduce((n, d) => n + submit("store", `Soi store ${d}`, {domain: d, country}), 0);
}

// ---- tự đào từ khoá: lấy từ tên sản phẩm / nội dung của các video đang hot mà bạn chưa quét ----

const STOP = new Set(["the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "your", "you", "my", "our", "is", "it",
  "this", "that", "new", "best", "get", "now", "buy", "shop", "free", "off", "sale", "just", "every", "from",
  "at", "by", "be", "are", "was", "will", "can", "all", "more", "most", "how", "why", "what", "who", "its"]);

function phrase(words, n) {
  words = words.filter(w => !STOP.has(w) && !/^\d+$/.test(w) && w.length > 1);
  return words.length >= 2 ? words.slice(0, n).join(" ") : null;
}

// Từ khoá đã quét (QC có từ khoá) hoặc đang tự quét mỗi đêm, chữ thường
export async function knownKeywords() {
  const known = new Set((await db.listWatchKeywords()).map(w => w.keyword.toLowerCase()));
  for (const a of await db.allAds()) if (a.keyword) known.add(a.keyword.toLowerCase());
  return known;
}

export async function keywordSuggestions(limit = 30) {
  const known = new Set((await db.listWatchKeywords()).map(w => w.keyword.toLowerCase()));
  for (const a of await db.allAds()) known.add((a.keyword || "").toLowerCase());
  const count = new Map(), source = new Map();
  for (const v of await db.listVideos()) {
    if (!(["sap_win", "win", "scale"].includes(v.label) || v.potential || v.cash_cow)) continue;
    const cands = [];
    if (v.product_key) cands.push([phrase(v.product_key.split("-"), 4), "tên sản phẩm"]);
    cands.push([phrase((v.title || "").toLowerCase().match(/[a-z0-9]+/g) || [], 3), "nội dung QC"]);
    for (const [kw, src] of cands) if (kw && !known.has(kw)) {
      count.set(kw, (count.get(kw) || 0) + 1);
      if (!source.has(kw)) source.set(kw, src);
    }
  }
  return [...count.keys()].sort((a, b) => (count.get(b) - count.get(a)) || (a < b ? -1 : a > b ? 1 : 0)).slice(0, limit)
    .map(k => ({keyword: k, videos: count.get(k), source: source.get(k)}));
}


export function socialTitle(platform, keyword, country) {
  return `Viral ${platform} '${keyword}'` + (social.MARKET_SOURCES.has(platform) ? ` ${country}` : "");
}

// {video, image, local, name} của 1 QC (ad) / 1 video QC (video) / 1 video viral (social). Không có -> null.
export async function mediaTarget(kind, key) {
  if (kind === "ad") {
    const a = (await db.allAds()).find(x => x.ad_id === key);
    if (!a) return null;
    const local = (await db.thumbData([a.thumb_path]))[a.thumb_path] || null;
    return {video: a.video_url, image: a.thumb_url, local, name: `qc-${key}-${media.slug(a.body || a.title)}`};
  }
  if (kind === "video") {
    const v = await db.getVideo(key);
    if (!v) return null;
    const local = (await db.thumbData([v.thumb]))[v.thumb] || null;
    return {video: v.video_url, image: v.thumb_url, local, name: `${v.label}-${media.slug(v.title)}-${key}`};
  }
  const r = await db.socialRow(key);
  if (!r) return null;
  const local = (await db.thumbData([r.cover_path]))[r.cover_path] || null;
  return {video: r.video_url, image: r.cover_url, local, name: `${r.platform}-${media.slug(r.caption)}-${r.item_id}`};
}
