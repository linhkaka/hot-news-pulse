// Gói chẩn đoán (giống snakepod/diag.py): khi 1 lượt quét ra 0 kết quả / lỗi / gặp checkpoint, lưu lại
// những gì trang trả về để người hỗ trợ sửa bộ đọc dữ liệu nhanh, không phải đoán.
//
// Mỗi gói tải về là 1 file .zip: meta.json, page.html, responses.jsonl, screenshot.png.
// Email trong dữ liệu được che (***@***). Trang có thể chứa tên tài khoản đang đăng nhập — xem trước khi gửi.
import * as db from "./db.js";

export const KEEP = 15;                 // giữ 15 gói gần nhất
export const MAX_RESPONSES = 40;
const MAX_RESPONSE_CHARS = 300000;
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

const scrub = text => String(text || "").replace(EMAIL_RE, "***@***");
const slug = s => (String(s || "scan").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40)) || "scan";
const pad = n => String(n).padStart(2, "0");

function stamp(d = new Date()) {
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

// Lưu 1 gói, trả về tên gói.
export async function save({label, url, finalUrl = null, html = null, responses = [], error = null, items = 0, screenshot = null}) {
  const existing = new Set((await db.getAll("diag")).map(b => b.name));
  const base = stamp() + "_" + slug(label);
  let name = base, n = 1;
  while (existing.has(name)) name = `${base}-${++n}`;
  const meta = {label, url, final_url: finalUrl, error, items, responses: responses.length, ts: db.now()};
  const rows = responses.slice(0, MAX_RESPONSES).map(([u, text]) => ({url: u, body: scrub(String(text).slice(0, MAX_RESPONSE_CHARS))}));
  await db.put("diag", {name, meta, html: html ? scrub(html) : null, responses: rows, screenshot});
  await prune();
  return name;
}

async function prune() {
  const names = (await db.getAll("diag")).map(b => b.name).sort();
  for (const old of names.slice(0, Math.max(0, names.length - KEEP))) await db.del("diag", old);
}

const enc = new TextEncoder();

function files(b) {
  const out = [["meta.json", enc.encode(JSON.stringify(b.meta, null, 2))]];
  if (b.html) out.push(["page.html", enc.encode(b.html)]);
  out.push(["responses.jsonl", enc.encode(b.responses.map(r => JSON.stringify(r) + "\n").join(""))]);
  if (b.screenshot) {
    const raw = atob(b.screenshot.split(",")[1]);
    out.push(["screenshot.png", Uint8Array.from(raw, c => c.charCodeAt(0))]);
  }
  return out;
}

export async function listBundles() {
  const all = (await db.getAll("diag")).sort((a, b) => (a.name < b.name ? 1 : -1));
  return all.map(b => ({name: b.name, size: files(b).reduce((s, [, d]) => s + d.length, 0), ...b.meta}));
}

// ---- file .zip tối giản (không nén), đủ để mở bằng Windows / 7-Zip ----

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(data) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < data.length; i++) c = CRC[(c ^ data[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

export function makeZip(entries) {
  const chunks = [], central = [];
  let offset = 0;
  for (const [name, data] of entries) {
    const nm = enc.encode(name), crc = crc32(data);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true); local.setUint16(4, 20, true); local.setUint16(6, 0x0800, true);
    local.setUint32(14, crc, true); local.setUint32(18, data.length, true); local.setUint32(22, data.length, true);
    local.setUint16(26, nm.length, true);
    chunks.push(new Uint8Array(local.buffer), nm, data);
    const cen = new DataView(new ArrayBuffer(46));
    cen.setUint32(0, 0x02014b50, true); cen.setUint16(4, 20, true); cen.setUint16(6, 20, true); cen.setUint16(8, 0x0800, true);
    cen.setUint32(16, crc, true); cen.setUint32(20, data.length, true); cen.setUint32(24, data.length, true);
    cen.setUint16(28, nm.length, true); cen.setUint32(42, offset, true);
    central.push(new Uint8Array(cen.buffer), nm);
    offset += 30 + nm.length + data.length;
  }
  const cenSize = central.reduce((s, c) => s + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true);
  end.setUint32(12, cenSize, true); end.setUint32(16, offset, true);
  const all = [...chunks, ...central, new Uint8Array(end.buffer)];
  const out = new Uint8Array(all.reduce((s, c) => s + c.length, 0));
  let p = 0;
  for (const c of all) { out.set(c, p); p += c.length; }
  return out;
}

// Nén 1 gói thành zip (base64, để gửi sang trang giao diện). Tên không có -> null.
export async function zipBundle(name) {
  const b = await db.get("diag", name);
  if (!b) return null;
  const zip = makeZip(files(b).map(([f, d]) => [`${name}/${f}`, d]));
  let s = "";
  for (let i = 0; i < zip.length; i += 0x8000) s += String.fromCharCode(...zip.subarray(i, i + 0x8000));
  return btoa(s);
}
