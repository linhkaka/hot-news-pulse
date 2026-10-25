// Mở Thư viện quảng cáo Facebook / TikTok trong 1 cửa sổ Chrome riêng, cuộn trang và đọc dữ liệu
// (giống snakepod/scraper.py, nhưng chạy ngay trong Chrome của bạn nên dùng luôn tài khoản đang đăng nhập).
//
// Dữ liệu lấy từ 2 nguồn:
//   - JSON nhúng sẵn trong trang lúc tải (script type="application/json");
//   - phản hồi mạng (GraphQL / API) mà content/hook.js bắt được rồi gửi về đây.
import {C, URLS} from "./config.js";
import * as safety from "./safety.js";
import * as diag from "./diag.js";
import * as social from "./social.js";
import * as kwtrends from "./kwtrends.js";
import {parseJsonText} from "./fbparser.js";

const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (lo, hi) => lo + Math.floor(Math.random() * (hi - lo + 1));
const qs = params => new URLSearchParams(params).toString();

// ---------------- địa chỉ trang ----------------

const fbBase = () => `${URLS.FB}/ads/library/`;

export const keywordUrl = (keyword, country) => fbBase() + "?" + qs({active_status: "all", ad_type: "all", country,
  is_targeted_country: "false", media_type: "video", q: keyword, search_type: "keyword_unordered"});

export const pageUrl = (pageId, country) => fbBase() + "?" + qs({active_status: "all", ad_type: "all", country,
  is_targeted_country: "false", media_type: "video", search_type: "page", view_all_page_id: pageId});

// '#dogmom' -> trang hashtag; còn lại -> tìm kiếm video
export function tiktokUrl(keyword) {
  const kw = keyword.trim();
  if (kw.startsWith("#")) return `${URLS.TIKTOK}/tag/${encodeURIComponent(kw.slice(1))}`;
  return `${URLS.TIKTOK}/search/video?` + qs({q: kw});
}

export const topadsUrl = (country, period) => URLS.CREATIVE_CENTER + "?" + qs({period, region: country});
// Creative Center: video thịnh hành / hashtag xu hướng của 1 thị trường
export const trendUrl = (base, country, period) => base + "?" + qs({period, countryCode: country, region: country});
export const reelsUrl = keyword => `${URLS.FB}/search/videos/?` + qs({q: keyword});

// ---------------- phiên quét: tab nào đang được quét ----------------

const sessions = new Map();   // tabId -> {match, push}

export const isScanTab = tabId => sessions.has(tabId);

// Gọi từ sw.js khi content script gửi 1 phản hồi mạng. Trả về true nếu tab đó đang được quét.
export function captured(tabId, url, text) {
  const s = sessions.get(tabId);
  if (!s) return false;
  if (s.match(url)) s.push([url, text]);
  return true;
}

// ---------------- điều khiển tab ----------------

async function run(tabId, func, args = []) {
  const [r] = await chrome.scripting.executeScript({target: {tabId}, func, args});
  return r ? r.result : undefined;
}

// Các hàm dưới đây chạy BÊN TRONG trang (phải tự đủ, không dùng biến bên ngoài)
function pageState(sel) {
  return {title: document.title, captcha: !!document.querySelector(sel), hidden: document.visibilityState === "hidden"};
}
function ssrTexts(markers) {
  return Array.from(document.querySelectorAll('script[type="application/json"]'), s => s.textContent || "")
    .filter(t => markers.some(m => t.includes(m)));
}
function scrollPage(dy) {
  window.dispatchEvent(new WheelEvent("wheel", {deltaY: dy, bubbles: true}));
  window.scrollBy(0, dy);
}
function clickMore(pattern) {
  const rx = new RegExp(pattern, "i");
  for (const el of document.querySelectorAll('button, a, [role="button"], div, span')) {
    if (el.children.length > 2 || !rx.test((el.innerText || "").trim())) continue;
    const r = el.getBoundingClientRect();
    if (r.width && r.height) { el.click(); return true; }
  }
  return false;
}
function typeSearch(keyword) {
  const box = Array.from(document.querySelectorAll("input")).find(i => /search/i.test(i.placeholder || ""));
  if (!box) return false;
  box.focus();
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  setter.call(box, keyword);
  box.dispatchEvent(new Event("input", {bubbles: true}));
  box.dispatchEvent(new Event("change", {bubbles: true}));
  for (const type of ["keydown", "keypress", "keyup"])
    box.dispatchEvent(new KeyboardEvent(type, {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
  if (box.form) box.form.requestSubmit();
  return true;
}
const outerHtml = () => document.documentElement.outerHTML;

// Đợi trang mới tải xong phần chính (DOMContentLoaded), tối đa 60 giây.
function navigate(tabId, url, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const done = (fn, v) => {
      clearTimeout(timer);
      chrome.webNavigation.onDOMContentLoaded.removeListener(onLoad);
      chrome.webNavigation.onErrorOccurred.removeListener(onErr);
      fn(v);
    };
    const onLoad = d => { if (d.tabId === tabId && d.frameId === 0 && d.url !== "about:blank") done(resolve); };
    const onErr = d => {
      if (d.tabId === tabId && d.frameId === 0 && d.error !== "net::ERR_ABORTED") done(reject, new Error(`Không mở được trang: ${d.error}`));
    };
    const timer = setTimeout(() => done(reject, new Error("Trang tải quá lâu (60 giây)")), timeoutMs);
    chrome.webNavigation.onDOMContentLoaded.addListener(onLoad);
    chrome.webNavigation.onErrorOccurred.addListener(onErr);
    chrome.tabs.update(tabId, {url}).catch(e => done(reject, e));
  });
}

// Gặp checkpoint / captcha / trang bắt đăng nhập -> ném CheckpointError để dừng ngay.
async function checkPage(platform, tabId) {
  const tab = await chrome.tabs.get(tabId).catch(() => { throw new Error("Cửa sổ quét đã bị đóng"); });
  let st = {title: tab.title || "", captcha: false, hidden: false};
  try { st = (await run(tabId, pageState, [safety.CAPTCHA_SELECTOR])) || st; } catch {}
  const reason = safety.detect(platform, tab.url, st.title || tab.title, st.captcha);
  if (reason) throw new safety.CheckpointError(platform, reason, tab.url);
  return st;
}

// 1 cửa sổ riêng cho mỗi lượt quét, đóng lại khi xong. Cửa sổ phải hiện trên màn hình:
// Chrome ngừng vẽ trang trong cửa sổ bị thu nhỏ / bị che hết, khi đó Facebook không tải thêm QC.
async function openScanWindow() {
  const w = await chrome.windows.create({url: "about:blank", focused: true, type: "normal", width: 1280, height: 900});
  return {windowId: w.id, tabId: w.tabs[0].id};
}

async function saveDiag(win, label, url, raws, error, nItems, log) {
  let html = null, shot = null, finalUrl = null;
  try { finalUrl = (await chrome.tabs.get(win.tabId)).url; } catch {}
  try { html = await run(win.tabId, outerHtml); } catch {}
  try { shot = await chrome.tabs.captureVisibleTab(win.windowId, {format: "png"}); } catch {}
  try {
    const name = await diag.save({label, url, finalUrl, html, responses: raws, error, items: nItems, screenshot: shot});
    log(`  Đã lưu gói chẩn đoán '${name}' (mục Chế độ an toàn → Gói chẩn đoán)`);
  } catch (e) {   // không để lỗi lưu chẩn đoán che lỗi thật
    log(`  Không lưu được gói chẩn đoán: ${e.message}`);
  }
}

// Mở 1 trang, cuộn tới khi đủ maxItems hoặc hết kết quả, đọc dữ liệu từ JSON trong trang + phản hồi mạng.
// Mặc định cho Thư viện QC Facebook; TikTok / Facebook Reels truyền bộ lọc và bộ đọc riêng.
export async function collect(url, maxItems, log, stop = () => false, {
  match = u => u.includes("/api/graphql"), marker = "ad_archive_id", parseText = parseJsonText, ssr = true,
  key = "ad_id", noun = "QC", platform = "facebook", clickMorePattern = null, prepare = null, label = null,
  win = null, progress = null,
} = {}) {
  const markers = [].concat(marker);
  const own = !win;
  win = win || await openScanWindow();
  const items = new Map(), raws = [], pending = [];
  sessions.set(win.tabId, {match, push: r => pending.push(r)});
  const drain = () => {
    while (pending.length) {
      const [u, text] = pending.shift();
      if (raws.length < diag.MAX_RESPONSES) raws.push([u, text]);
      if (markers.some(m => text.includes(m))) for (const it of parseText(text)) items.set(it[key], it);
    }
  };
  let warned = false;
  const check = async () => {
    const st = await checkPage(platform, win.tabId);
    if (st.hidden && !warned) {
      warned = true;
      log("  ⚠ Cửa sổ quét đang bị thu nhỏ hoặc bị che: Chrome ngừng tải trang ẩn. Hãy để cửa sổ quét hiện trên màn hình.");
    }
  };
  try {
    await navigate(win.tabId, url);
    await sleep(C.LOAD_WAIT_MS);
    await check();
    if (prepare) {
      await prepare(win.tabId, log);
      await sleep(C.PREPARE_WAIT_MS);
      await check();
    }
    if (ssr) for (const text of (await run(win.tabId, ssrTexts, [markers])) || [])
      for (const it of parseText(text)) items.set(it[key], it);
    drain();
    let stale = 0, rounds = 0;
    const [lo, hi] = C.SCROLL_PAUSE_MS;
    while (items.size < maxItems && stale < 5 && rounds < C.MAX_SCROLL_ROUNDS && !stop()) {
      rounds++;
      const before = items.size;
      if (clickMorePattern) { try { await run(win.tabId, clickMore, [clickMorePattern]); } catch {} }
      await run(win.tabId, scrollPage, [rand(2500, 5000)]).catch(() => {});
      await sleep(rand(lo, hi));
      await check();
      drain();
      stale = items.size === before ? stale + 1 : 0;
      if (items.size !== before) {
        log(`  ... đã đọc ${items.size} ${noun}`);
        if (progress) progress(items.size);
      }
    }
    drain();
    if (!items.size) await saveDiag(win, label || `${platform}-${noun}`, url, raws, "Không đọc được kết quả nào", 0, log);
  } catch (e) {
    await saveDiag(win, label || `${platform}-${noun}`, url, raws, String(e.message || e).slice(0, 500), items.size, log);
    throw e;
  } finally {
    sessions.delete(win.tabId);
    if (own) await chrome.windows.remove(win.windowId).catch(() => {});
  }
  return [...items.values()].slice(0, maxItems);
}

export const scanKeyword = (keyword, country, maxAds, log, stop, progress = null) =>
  collect(keywordUrl(keyword, country), maxAds, log, stop, {progress});

export async function scanPages(pageIds, country, maxAds, log, stop = () => false, progress = null) {
  const out = [];
  const win = await openScanWindow();
  try {
    for (let i = 0; i < pageIds.length; i++) {
      if (stop()) break;
      if (i) {
        const gap = rand(...C.PAGE_GAP_S);
        log(`Nghỉ ${gap} giây trước page tiếp theo (chế độ an toàn)`);
        for (let s = 0; s < gap && !stop(); s++) await sleep(1000);
      }
      log(`Đào page ${pageIds[i]}`);
      const b = out.length;
      out.push(...await collect(pageUrl(pageIds[i], country), maxAds, log, stop, {win, progress: progress && (n => progress(b + n))}));
    }
  } finally {
    await chrome.windows.remove(win.windowId).catch(() => {});
  }
  return out;
}

// ---------------- Video viral: TikTok + Facebook Reels ----------------

const TIKTOK_API = ["/api/search/", "/api/challenge/item_list", "/api/post/item_list"];

// Creative Center: gõ từ khoá vào ô tìm kiếm (nếu có) rồi Enter.
const typeKeyword = keyword => async (tabId, log) => {
  if (!keyword) return;
  try {
    if (await run(tabId, typeSearch, [keyword])) log(`Tìm '${keyword}' trong Top Ads`);
    else log("Không thấy ô tìm kiếm trong Top Ads; lấy Top Ads chung");
  } catch (e) { log(`Không gõ được từ khoá vào Top Ads (${e.message}); lấy Top Ads chung`); }
};

// Pinterest Trends của 1 thị trường: đọc lỏng mọi JSON của trang có từ khoá + % tăng trưởng (thử nghiệm).
export const scanPinterest = (geo, maxItems, log, stop = () => false) =>
  collect(URLS.PINTEREST_TRENDS.replace("{geo}", geo), maxItems, log, stop, {
    match: u => u.includes("trends") || u.includes("/resource/"), marker: ["growth", "pct_"],
    parseText: kwtrends.parsePinterestText, key: "term", noun: "từ khoá", platform: "pinterest"});

export function scanSocial(platform, keyword, country, maxItems, period, log, stop = () => false, progress = null) {
  if (platform === "tiktok") return collect(tiktokUrl(keyword), maxItems, log, stop, {progress,
    match: u => TIKTOK_API.some(k => u.includes(k)), marker: "playCount", parseText: social.parseTiktokText,
    key: "vid", noun: "video", platform: "tiktok"});
  if (platform === "tiktok_ads") return collect(topadsUrl(country, period), maxItems, log, stop, {progress,
    match: u => u.includes("creative_radar_api"), marker: "ad_title", parseText: social.parseTopadsText, ssr: false,
    key: "vid", noun: "Top Ads", platform: "tiktok", clickMorePattern: "View More|Xem thêm", prepare: typeKeyword(keyword)});
  if (platform === "tiktok_trend") return collect(trendUrl(URLS.TREND_VIDEOS, country, period), maxItems, log, stop, {progress,
    match: u => u.includes("creative_radar_api"), marker: ["item_url", "item_id"], parseText: social.parseTrendVideosText,
    key: "vid", noun: "video thịnh hành", platform: "tiktok", clickMorePattern: "View More|Xem thêm"});
  if (platform === "tiktok_tags") return collect(trendUrl(URLS.TREND_TAGS, country, period), maxItems, log, stop, {progress,
    match: u => u.includes("creative_radar_api"), marker: "hashtag_name", parseText: social.parseHashtagsText,
    key: "name", noun: "hashtag", platform: "tiktok", clickMorePattern: "View More|Xem thêm"});
  if (platform === "fb_reels") return collect(reelsUrl(keyword), maxItems, log, stop, {progress,
    marker: ["play_count", "video_view_count"], parseText: social.parseReelsText, key: "vid", noun: "video"});
  throw new Error(`Nền tảng không hỗ trợ: ${platform}`);
}
