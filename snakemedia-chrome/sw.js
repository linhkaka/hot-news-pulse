// Phần nền của tiện ích SNAKEMEDIA POD: nhận lệnh từ giao diện, chạy hàng đợi quét, lịch tự quét mỗi đêm,
// và nhận dữ liệu mà content script bắt được trên Facebook / TikTok.
import {C, URLS, CAPTURE_MATCHES, DEV, applyDev} from "./lib/config.js";
import * as db from "./lib/db.js";
import * as api from "./lib/api.js";
import * as jobs from "./lib/jobs.js";
import * as scanner from "./lib/scanner.js";
import * as analyze from "./lib/analyze.js";
import * as fbparser from "./lib/fbparser.js";
import * as landing from "./lib/landing.js";
import * as pod from "./lib/pod.js";
import * as safety from "./lib/safety.js";
import * as social from "./lib/social.js";
import * as notify from "./lib/notify.js";
import * as diag from "./lib/diag.js";
import * as imagehash from "./lib/imagehash.js";
import * as shopify from "./lib/shopify.js";
import * as kwtrends from "./lib/kwtrends.js";

// Gắn bộ bắt dữ liệu vào các trang cần quét (thêm trang giả trên máy khi chạy bài kiểm thử)
async function registerCapture() {
  const matches = [...CAPTURE_MATCHES, ...DEV.matches];
  const old = await chrome.scripting.getRegisteredContentScripts();
  if (old.length) await chrome.scripting.unregisterContentScripts({ids: old.map(s => s.id)});
  await chrome.scripting.registerContentScripts([
    {id: "hook", js: ["content/hook.js"], matches, runAt: "document_start", world: "MAIN", persistAcrossSessions: true},
    {id: "agent", js: ["content/agent.js"], matches, runAt: "document_start", persistAcrossSessions: true},
  ]);
}

async function init() {
  const {dev} = await chrome.storage.local.get("dev");
  applyDev(dev);
  await registerCapture();
  await chrome.alarms.create("tick", {periodInMinutes: 1});
  await db.fixSocialWatchCountry().catch(e => console.error(e));
  await jobs.restore();
  // Cập nhật lên bản có tab Tiềm năng / Bò sữa / lịch sử: chấm lại 1 lần để video cũ có đủ số liệu mới
  if ((await db.getSetting("schema", 1)) < 2) {
    await db.setSetting("schema", 2);
    if (await db.count("ads")) jobs.submit("recompute", "Chấm lại (bản nâng cấp)", {});
  }
}
const ready = init().catch(e => console.error("Khởi động lỗi", e));

chrome.runtime.onInstalled.addListener(d => {
  if (d.reason === "install") chrome.tabs.create({url: chrome.runtime.getURL("dashboard.html")});
});

chrome.alarms.onAlarm.addListener(async a => {
  await ready;
  if (a.name === "tick") jobs.schedulerTick().catch(e => jobs.log(`Lỗi lịch tự quét: ${e.message}`));
});

chrome.action.setBadgeBackgroundColor({color: "#0a9a96"}).catch(() => {});

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    await ready;
    // Lệnh điều khiển chỉ nhận từ trang của chính tiện ích (bảng điều khiển, popup), không nhận từ Facebook/TikTok
    if (msg.type === "api") {
      if (!String(sender.url || "").startsWith(chrome.runtime.getURL(""))) return {ok: false, status: 403, detail: "Forbidden"};
      return api.handle(msg);
    }
    const tabId = sender.tab && sender.tab.id;
    if (msg.type === "cap" && tabId !== undefined) {
      if (scanner.captured(tabId, msg.url, msg.text)) return {ok: true};
      return {saved: await jobs.passiveCapture(sender.tab.url, [msg.text])};
    }
    if (msg.type === "ssr" && tabId !== undefined && !scanner.isScanTab(tabId))
      return {saved: await jobs.passiveCapture(msg.url, msg.texts || [])};
    return {ok: false};
  })().then(reply, e => reply({ok: false, status: 500, detail: String(e && e.message || e)}));
  return true;   // trả lời bất đồng bộ
});

// Bài kiểm thử gọi các hàm này trực tiếp (service worker không cho import() động)
self.SP = {C, URLS, db, api, jobs, scanner, analyze, fbparser, landing, pod, safety, social, notify, diag, imagehash, shopify, kwtrends, ready,
  async setDev(dev) {
    await chrome.storage.local.set({dev});
    applyDev(dev);
    await registerCapture();
  }};
