// Hàng đợi việc chạy nền (quét, đào sâu) + nhật ký hiển thị trên giao diện (giống snakepod/jobs.py).
//
// Mỗi việc là dữ liệu {kind, title, args} và được lưu lại, nên Chrome tắt giữa chừng thì lần mở sau
// các việc còn chờ vẫn chạy tiếp.
import {C} from "./config.js";
import * as db from "./db.js";
import * as analyze from "./analyze.js";
import * as landing from "./landing.js";
import * as notify from "./notify.js";
import * as safety from "./safety.js";
import * as scanner from "./scanner.js";
import * as social from "./social.js";
import * as demo from "./demo.js";
import {fetchImage} from "./imagehash.js";
import {parseJsonText} from "./fbparser.js";

const LOG = [];
const state = {current: null, pending: [], stop: false, running: false};
const hasStorage = () => globalThis.chrome && chrome.storage && chrome.storage.local;

function persist() {
  if (hasStorage()) chrome.storage.local.set({jobs: {pending: state.pending, current: state.current, log: LOG}}).catch(() => {});
}

export function log(msg) {
  LOG.push({ts: db.now(), msg});
  if (LOG.length > 300) LOG.splice(0, LOG.length - 300);
  console.log(new Date().toLocaleTimeString(), msg);
  persist();
}

export async function status() {
  return {current: state.current, pending: state.pending.map(j => j.title), log: LOG.slice(-80), blocked: await safety.blocked()};
}

// Xếp việc vào hàng đợi. Bỏ qua nếu việc trùng tên đang chờ/đang chạy.
export function submit(kind, title, args = {}) {
  if (state.pending.some(j => j.title === title) || state.current === title) return false;
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
  if (jobs.current) log(`Việc '${jobs.current}' bị gián đoạn (Chrome tắt hoặc tiện ích khởi động lại)`);
  for (const j of jobs.pending || []) if (!state.pending.some(p => p.title === j.title)) state.pending.push(j);
  persist();
  kick();
}

function kick() {
  if (state.running) return;
  state.running = true;
  runLoop().finally(() => { state.running = false; });
}

async function runLoop() {
  while (state.pending.length) {
    const job = state.pending.shift();
    state.current = job.title;
    state.stop = false;
    persist();
    // Giữ phần nền của tiện ích thức trong lúc chạy việc dài (Chrome tự tắt phần nền rảnh sau 30 giây)
    const keepAlive = setInterval(() => chrome.runtime.getPlatformInfo().catch(() => {}), 20000);
    const scanId = await db.startScan(job.kind, job.title);
    try {
      const n = (await JOBS[job.kind](job.args)) || 0;
      await db.finishScan(scanId, state.stop ? "da dung" : "xong", n);
      log(`Xong: ${job.title}`);
    } catch (e) {
      if (e instanceof safety.Skipped) {
        await db.finishScan(scanId, "bo qua", 0, String(e.message).slice(0, 500));
        log(`Bỏ qua '${job.title}': ${e.message}`);
      } else if (e instanceof safety.CheckpointError) {
        await safety.block(e.platform, e.reason, e.url);
        await db.finishScan(scanId, "checkpoint", 0, e.reason);
        log(`⚠ ${e.reason}. ĐÃ TẠM DỪNG mọi lượt quét ${safety.PLATFORMS[e.platform]}. ` +
          "Hãy tự xác minh trên Facebook/TikTok rồi bấm 'Đã xử lý, quét tiếp'.");
        await notify.send(`⚠ SNAKEMEDIA POD: ${e.reason}`, ["Đã tạm dừng quét để bảo vệ tài khoản."], log).catch(() => {});
      } else {
        await db.finishScan(scanId, "loi", 0, String(e && e.message || e).slice(0, 500));
        log(`Lỗi khi chạy '${job.title}': ${e && e.message || e}`);
      }
    } finally {
      clearInterval(keepAlive);
      state.current = null;
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
    const ads = await scanner.scanKeyword(keyword, country, max_ads, log, shouldStop);
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
      ads = await scanner.scanPages([key], country, C.DIG_MAX_ADS_PER_PAGE, log, shouldStop);
    } else {
      log(`Quét shop ${key}`);
      ads = await scanner.scanKeyword(key, country, C.DEFAULT_MAX_ADS, log, shouldStop);
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

  // Quét video viral 1 nền tảng theo từ khoá (Top Ads: từ khoá có thể bỏ trống).
  async social({platform, keyword, country, max_items, period = 7}) {
    await demo.clearIfDemo(log);
    const name = social.PLATFORMS[platform];
    log(`Quét ${name} '${keyword || "tất cả"}' (${country})`);
    await safety.beforeScan(safety.platformOf(platform), log, shouldStop);
    const items = await scanner.scanSocial(platform, keyword, country, max_items, period, log, shouldStop);
    log(`Đọc được ${items.length} video ${name}`);
    await db.upsertSocial(items, keyword || null);
    await db.touchSocialWatch(platform, keyword);
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
    const ads = await scanner.scanPages(pages, country, C.DIG_MAX_ADS_PER_PAGE, log, shouldStop);
    await db.upsertAds(ads);
    await processAfterScan();
    return ads.length;
  },

  async recompute() { await recompute(); return 0; },

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
export async function passiveCapture(pageUrl, texts) {
  if (!(await passiveEnabled())) return 0;
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
    n += submit("follow", `Theo dõi ${f.kind} ${f.name || f.key}`, {kind: f.kind, key: f.key, country});
  for (const w of await db.listSocialWatch())
    n += submit("social", `Viral ${w.platform} '${w.keyword}'`,
      {platform: w.platform, keyword: w.keyword, country: w.country || country, max_items: C.DEFAULT_MAX_ADS});
  log(`${reason}: xếp ${n} việc quét`);
  return n;
}

export async function autoSettings() {
  return {enabled: true, hour: C.AUTO_SCAN_HOUR, last_date: null, ...(await db.getSetting("auto", {}))};
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
