// Thông báo khi có hàng đáng xem: Telegram (điện thoại) và thông báo của Chrome (giống snakepod/notify.py).
//
// Báo khi:
//   - video QC Facebook mới vào nhãn Sắp WIN / Video Win;
//   - video TikTok / Reels mới vào nhãn Đang nổ / Viral;
//   - page/shop đang theo dõi vừa lên QC mới.
// Mỗi thứ chỉ báo 1 lần (bảng `notified`). Video đã có từ trước khi bật thông báo được ghi nhận im lặng.
import * as db from "./db.js";
import {URLS} from "./config.js";
import {pyNum} from "./social.js";

const DEFAULT = {telegram_token: "", telegram_chat_id: "", desktop: true,
  events: {sap_win: true, win: true, viral: true, follow: true}};
const MAX_ITEMS_PER_MESSAGE = 5;

export const escHtml = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;"}[c]));

export async function settings() {
  const s = await db.getSetting("notify", {});
  return {...DEFAULT, ...s, events: {...DEFAULT.events, ...(s.events || {})}};
}

// Cho giao diện: không trả nguyên token.
export async function publicSettings() {
  const s = await settings();
  const tok = s.telegram_token;
  delete s.telegram_token;
  return {...s, has_token: !!tok, token_hint: tok ? "…" + tok.slice(-4) : ""};
}

export async function saveSettings({telegram_token = null, telegram_chat_id = null, desktop = null, events = null} = {}) {
  const s = await settings();
  if (telegram_token !== null && telegram_token.trim() !== "") s.telegram_token = telegram_token.trim();
  if (telegram_token === "") s.telegram_token = "";       // gửi chuỗi rỗng có chủ đích = xoá token
  if (telegram_chat_id !== null) s.telegram_chat_id = String(telegram_chat_id).trim();
  if (desktop !== null) s.desktop = !!desktop;
  if (events) for (const [k, v] of Object.entries(events)) if (k in DEFAULT.events) s.events[k] = !!v;
  await db.setSetting("notify", s);
}

// ---------------- kênh gửi ----------------

async function tgCall(token, method, body = null) {
  const r = await fetch(`${URLS.TG_API}/bot${token}/${method}`, body
    ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {});
  let data;
  try { data = await r.json(); } catch { throw new Error(`Telegram trả lỗi ${r.status}`); }
  if (!data.ok) throw new Error(data.description || `Telegram trả lỗi ${r.status}`);
  return data;
}

export const sendTelegram = (token, chatId, text) =>
  tgCall(token, "sendMessage", {chat_id: chatId, text, parse_mode: "HTML", disable_web_page_preview: true});

// Lấy chat ID từ tin nhắn gần nhất người dùng gửi cho bot (bước 'nhắn /start cho bot').
export async function findChatId(token) {
  const data = await tgCall(token, "getUpdates");
  for (const upd of [...(data.result || [])].reverse()) {
    const chat = (upd.message || upd.channel_post || {}).chat;
    if (chat && chat.id !== null && chat.id !== undefined) return String(chat.id);
  }
  return null;
}

// Thông báo góc màn hình của Chrome (Windows / macOS / Linux)
export async function desktopNotify(title, body) {
  if (!globalThis.chrome || !chrome.notifications) return false;
  await chrome.notifications.create("", {type: "basic", iconUrl: chrome.runtime.getURL("icons/icon128.png"),
    title: title.slice(0, 120), message: body.slice(0, 250), priority: 1});
  return true;
}

const plain = line => line.replace(/<[^>]+>/g, "").replace(/&(amp|lt|gt|quot|#x27);/g,
  (_, e) => ({amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'"}[e]));

// Gửi 1 thông báo tới mọi kênh đang bật. Lỗi 1 kênh không chặn kênh khác.
export async function send(title, lines, log = console.log) {
  const s = await settings();
  const sent = [];
  if (s.telegram_token && s.telegram_chat_id) {
    try {
      await sendTelegram(s.telegram_token, s.telegram_chat_id, `<b>${escHtml(title)}</b>\n` + lines.join("\n"));
      sent.push("telegram");
    } catch (e) { log(`Không gửi được Telegram: ${e.message}`); }
  }
  if (s.desktop) {
    try { if (await desktopNotify(title, lines.length ? plain(lines[0]) : "")) sent.push("chrome"); }
    catch (e) { log(`Không hiện được thông báo Chrome: ${e.message}`); }
  }
  return sent;
}

// ---------------- phát hiện cái mới ----------------

// Trong `keys`, những cái chưa từng báo. Đồng thời đánh dấu tất cả là đã báo.
async function fresh(kind, keys) {
  keys = [...new Set(keys)];
  const out = await db.unseenNotified(kind, keys);
  await db.markNotified(kind, keys);
  return out;
}

const link = (url, text) => url ? `<a href="${escHtml(url)}">${escHtml(text)}</a>` : escHtml(text);
const cut = (s, n) => Array.from(s || "").slice(0, n).join("");

async function batch(title, items, fmt, log) {
  if (!items.length) return [];
  const lines = items.slice(0, MAX_ITEMS_PER_MESSAGE).map(fmt);
  if (items.length > MAX_ITEMS_PER_MESSAGE)
    lines.push(`… và ${items.length - MAX_ITEMS_PER_MESSAGE} video khác (mở SNAKEMEDIA POD để xem)`);
  return send(`${title} (${items.length})`, lines, log);
}

// Gọi sau mỗi lần chấm lại video QC Facebook.
export async function checkVideos(videos, log = console.log) {
  const ev = (await settings()).events;
  let out = [];
  for (const [label, name] of [["sap_win", "Sắp WIN mới"], ["win", "Video Win mới"]]) {
    const cur = videos.filter(v => v.label === label);
    const newIds = new Set(await fresh(label, cur.map(v => v.cid)));
    const fresh_ = cur.filter(v => newIds.has(v.cid));
    if (ev[label] && fresh_.length)
      out = out.concat(await batch(`🐍 ${name}`, fresh_, v =>
        `• ${link(v.ad_library_url, cut(v.title, 80))} — video ${v.video_age_days ? pyNum(v.video_age_days) : "?"} ngày, ` +
        `${v.shops_active} shop, ${pyNum(v.ads_per_day)} QC/ngày`, log));
  }
  return out;
}

// Gọi sau mỗi lần quét video viral. `items` là kết quả social.summarize().
export async function checkSocial(items, log = console.log) {
  const ev = (await settings()).events;
  const cur = items.filter(v => v.label === "dang_no" || v.label === "viral");
  const newIds = new Set(await fresh("viral", cur.map(v => v.vid)));
  const fresh_ = cur.filter(v => newIds.has(v.vid)).sort((a, b) => (b.sort_vph || 0) - (a.sort_vph || 0));
  if (!(ev.viral && fresh_.length)) return [];
  return batch("🔥 Video viral mới", fresh_, v =>
    `• ${link(v.url, cut(v.caption || "video", 80))} — ${v.views || "?"} xem, ${v.vph || "?"}/giờ`, log);
}

export async function followUpdate(name, newAds, log = console.log) {
  if (newAds && (await settings()).events.follow)
    return send(`★ ${name} vừa lên ${newAds} QC mới`, [escHtml("Mở mục Theo dõi đặc biệt để xem.")], log);
  return [];
}
