// Chế độ an toàn: quét như một người dùng bình thường, và DỪNG NGAY khi nền tảng nghi ngờ
// (giống snakepod/safety.py).
//
// Tiện ích không che giấu việc tự động hoá (không giả dấu vân tay, không giải captcha, không xoay tài khoản).
// Thay vào đó nó giảm nguy cơ bị checkpoint bằng cách:
//   - nghỉ tối thiểu giữa 2 lần quét cùng nền tảng, cuộn trang chậm có ngẫu nhiên;
//   - giới hạn số lần quét mỗi ngày;
//   - phát hiện trang checkpoint / captcha / bắt đăng nhập -> tạm dừng mọi lượt quét của nền tảng đó
//     cho tới khi bạn tự xác minh và bấm "Đã xử lý, quét tiếp".
import * as db from "./db.js";
import {C} from "./config.js";

export const PLATFORMS = {facebook: "Facebook", tiktok: "TikTok"};
// Phần tử captcha phổ biến (Facebook, TikTok, reCAPTCHA, hCaptcha)
export const CAPTCHA_SELECTOR = '[id*="captcha" i], [class*="captcha" i], iframe[src*="captcha" i], ' +
  'iframe[src*="recaptcha" i], iframe[src*="hcaptcha" i]';

export class CheckpointError extends Error {
  constructor(platform, reason, url = null) { super(reason); this.platform = platform; this.reason = reason; this.url = url; }
}

// Lượt quét bị bỏ qua có chủ đích (đang tạm dừng / hết lượt trong ngày)
export class Skipped extends Error {}

// 'fb_reels', 'tiktok_ads', 'keyword'... -> 'facebook' | 'tiktok'
export const platformOf = source => (String(source).startsWith("tiktok") ? "tiktok" : "facebook");

// Trả về lý do (tiếng Việt) nếu trang đang là checkpoint / captcha / bắt đăng nhập, ngược lại null.
export function detect(platform, url, title = "", hasCaptcha = false) {
  const u = (url || "").toLowerCase(), t = (title || "").toLowerCase();
  const name = PLATFORMS[platform];
  if (platform === "facebook") {
    if (u.includes("/checkpoint") || t.includes("security check") || t.includes("kiểm tra bảo mật"))
      return "Facebook yêu cầu xác minh tài khoản (checkpoint)";
    if (u.includes("two_step_verification") || u.includes("/two_factor") || u.includes("/challenge"))
      return "Facebook yêu cầu xác minh 2 bước";
    if (u.includes("/login") || u.includes("login.php")) return "Facebook yêu cầu đăng nhập lại";
  } else {
    if (u.includes("/login")) return "TikTok yêu cầu đăng nhập lại";
    if (t.includes("verify") && t.includes("tiktok")) return "TikTok yêu cầu xác minh";
  }
  if (hasCaptcha) return `${name} hiện captcha (xác minh không phải robot)`;
  return null;
}

// ---------------- trạng thái + giới hạn ----------------

export async function limits() {
  const saved = await db.getSetting("safety_limits", {});
  return Object.fromEntries(Object.keys(PLATFORMS).map(p => [p, {...C.SAFETY_DEFAULT_LIMITS[p], ...(saved[p] || {})}]));
}

export async function setLimits(platform, minGapS, maxPerDay) {
  if (!(platform in PLATFORMS)) throw new RangeError("Nền tảng không hợp lệ");
  if (!(minGapS >= 30 && minGapS <= 3600 && maxPerDay >= 1 && maxPerDay <= 500))
    throw new RangeError("Nghỉ giữa 2 lần quét: 30–3600 giây; số lần quét/ngày: 1–500");
  const saved = await db.getSetting("safety_limits", {});
  saved[platform] = {min_gap_s: Math.trunc(minGapS), max_per_day: Math.trunc(maxPerDay)};
  await db.setSetting("safety_limits", saved);
}

export const blocked = () => db.getSetting("blocked", {});

export async function block(platform, reason, url = null) {
  const b = await blocked();
  b[platform] = {reason, url, ts: db.now()};
  await db.setSetting("blocked", b);
}

export async function resume(platform) {
  const b = await blocked();
  delete b[platform];
  await db.setSetting("blocked", b);
}

function midnight(t) {
  const d = new Date(t * 1000);
  d.setHours(0, 0, 0, 0);
  return Math.floor(d.getTime() / 1000);
}

export const usedToday = (platform, t = null) => db.countRateEvents(platform, midnight(t || db.now()));

const realSleep = ms => new Promise(r => setTimeout(r, ms));

// Kiểm tra trước mỗi lượt quét. Ném Skipped nếu không được quét; tự nghỉ cho đủ khoảng cách tối thiểu.
export async function beforeScan(platform, log, shouldStop = () => false, sleep = realSleep, now = () => Date.now() / 1000) {
  const name = PLATFORMS[platform];
  const b = (await blocked())[platform];
  if (b) throw new Skipped(`${name} đang tạm dừng vì: ${b.reason}. Xác minh xong hãy bấm 'Đã xử lý, quét tiếp'.`);
  const lim = (await limits())[platform];
  const used = await usedToday(platform, now());
  if (used >= lim.max_per_day)
    throw new Skipped(`Đã quét ${name} ${used}/${lim.max_per_day} lần hôm nay (giới hạn an toàn). Mai quét tiếp.`);
  const last = await db.lastRateEvent(platform);
  const wait = last ? Math.trunc(last + lim.min_gap_s - now()) : 0;
  if (wait > 0) {
    log(`Nghỉ ${wait} giây trước khi quét ${name} (chế độ an toàn)`);
    const end = now() + wait;
    while (now() < end) {
      if (shouldStop()) throw new Skipped("Đã dừng");
      await sleep(Math.min(1, end - now()) * 1000);
    }
  }
  await db.addRateEvent(platform, Math.trunc(now()));
}

export async function status() {
  const [lim, b] = await Promise.all([limits(), blocked()]);
  const out = [];
  for (const [p, n] of Object.entries(PLATFORMS))
    out.push({key: p, name: n, blocked: b[p] || null, used_today: await usedToday(p), last_ts: await db.lastRateEvent(p), ...lim[p]});
  return out;
}
