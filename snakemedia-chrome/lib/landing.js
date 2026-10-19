// Tuổi của trang bán (giống snakepod/landing.py).
//
// Thứ tự tin cậy (lấy nguồn đáng tin nhất tìm được):
//   1. "api"   - Shopify /products/<handle>.json, hoặc JSON sản phẩm nhúng trong trang có created_at
//   2. "uuid"  - mã sản phẩm dạng UUID phiên bản 1 (chứa sẵn thời điểm tạo) - hay gặp ở nền tảng Trung Quốc
//   3. "anh"   - mốc thời gian trong link ảnh sản phẩm (Shopify ?v=<unix>, /uploads/YYYY/MM/ ...)
// Nguồn 2-3 là ƯỚC TÍNH, giao diện sẽ ghi rõ.
import {detectPodMarkers} from "./pod.js";
import {urlparse} from "./fbparser.js";

const PRODUCT_RE = /(\/products?\/[^/?#]+)/;
const DATE_KEYS = '"(?:created_at|createdAt|create_time|created_time|published_at|publishedAt|datePublished|release_date)"';
const DATE_RE = new RegExp(DATE_KEYS + '\\s*:\\s*"?([0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+(?:Z|[+-][0-9:]{4,5})?|[0-9]{10,13})"?', "g");
const UUID_RE = /"(?:product_id|productId|id|spu_id)"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-1[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12})"/gi;
const IMG_V_RE = /(?:cdn\.shopify\.com|\/cdn\/shop)\/[^"'\s]+?\?v=(1[5-9][0-9]{8})/g;
const UPLOADS_RE = /\/uploads\/(20[1-3][0-9])\/(0[1-9]|1[0-2])\//g;
const TITLE_RE = /<title[^>]*>([\s\S]*?)<\/title>/i;
const MIN_TS = 1262304000;   // 2010-01-01: bỏ mốc vô lý

export function isoTs(s) {
  if (s === null || s === undefined || s === "") return null;
  s = String(s).trim();
  if (/^\d+$/.test(s)) {
    const v = parseInt(s.slice(0, 10), 10);
    return v > MIN_TS ? v : null;
  }
  s = s.replace("Z", "+00:00").replace(" ", "T");
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s)) return null;
  // Không có múi giờ -> coi là UTC (như bản Python); "+0700" -> "+07:00"
  if (!/[+-]\d{2}:?\d{2}$/.test(s)) s += "+00:00";
  s = s.replace(/([+-]\d{2})(\d{2})$/, "$1:$2");
  const ms = Date.parse(s);
  if (Number.isNaN(ms)) return null;
  const v = Math.floor(ms / 1000);
  return v > MIN_TS ? v : null;
}

// Thời điểm tạo nằm sẵn trong UUID phiên bản 1.
export function uuid1Ts(value) {
  const hex = String(value || "").replace(/-/g, "").toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(hex)) return null;
  if (hex[12] !== "1") return null;
  const timeLow = BigInt("0x" + hex.slice(0, 8)), timeMid = BigInt("0x" + hex.slice(8, 12));
  const timeHi = BigInt("0x" + hex.slice(12, 16)) & 0x0fffn;
  const t = (timeHi << 48n) | (timeMid << 32n) | timeLow;
  const ts = Number(t - 0x01B21DD213814000n) / 1e7;
  return MIN_TS < ts && ts < Date.now() / 1000 + 86400 ? Math.trunc(ts) : null;
}

export function detectPlatform(html) {
  const h = html.toLowerCase();
  if (h.includes("cdn.shopify.com") || h.includes("shopify.theme")) return "shopify";
  if (h.includes("shoplazza") || h.includes("staticdj.com")) return "shoplazza";
  if (h.includes("shopline")) return "shopline";
  if (h.includes("woocommerce")) return "woocommerce";
  const pods = detectPodMarkers(html);
  for (const name of ["shopbase", "gearlaunch", "teechip"]) if (pods.includes(name)) return name;
  return null;
}

export function parseShopifyProduct(data) {
  const p = (data && data.product) || {};
  const variants = p.variants || [];
  return {
    created_ts: isoTs(p.created_at),
    published_ts: isoTs(p.published_at),
    title: p.title ?? null,
    price: variants.length ? variants[0].price ?? null : null,
    compare_price: variants.length ? variants[0].compare_at_price || null : null,
  };
}

// Tìm ngày tạo sản phẩm trong trang. Trả về [ts, nguồn] hoặc [null, null].
export function datesFromHtml(html) {
  const found = [...html.matchAll(DATE_RE)].map(m => isoTs(m[1])).filter(Boolean);
  if (found.length) return [Math.min(...found), "api"];
  const ids = [...html.matchAll(UUID_RE)].map(m => uuid1Ts(m[1])).filter(Boolean);
  if (ids.length) return [Math.min(...ids), "uuid"];
  const imgs = [...html.matchAll(IMG_V_RE)].map(m => parseInt(m[1], 10));
  const ups = [...html.matchAll(UPLOADS_RE)].map(m => Date.UTC(+m[1], +m[2] - 1, 1) / 1000);
  const stamps = [...imgs, ...ups].filter(t => t > MIN_TS);
  if (stamps.length) return [Math.min(...stamps), "anh"];
  return [null, null];
}

function priceFromHtml(html) {
  const m = /"price"\s*:\s*"?([0-9]+(?:\.[0-9]{1,2})?)"?/.exec(html);
  return m ? m[1] : null;
}

async function fetchText(url, timeoutMs = 20000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {signal: ctl.signal, credentials: "omit", redirect: "follow"});
    return {status: r.status, url: r.url || url, type: r.headers.get("content-type") || "", text: await r.text()};
  } finally {
    clearTimeout(timer);
  }
}

export async function check(url) {
  const info = {url, final_url: null, domain: null, platform: null, created_ts: null, published_ts: null, title: null,
    price: null, checked_ts: Math.floor(Date.now() / 1000), error: null, date_source: null, pod_markers: null,
    compare_price: null};
  try {
    const r = await fetchText(url);
    const html = r.text;
    info.final_url = r.url;
    const p = urlparse(r.url);
    const netloc = p.netloc.toLowerCase();
    info.domain = netloc.startsWith("www.") ? netloc.slice(4) : netloc;
    info.platform = detectPlatform(html);
    info.pod_markers = detectPodMarkers(html).join(",") || null;
    const m = PRODUCT_RE.exec(p.path);
    if (m && m[1].startsWith("/products/")) {
      try {
        const j = await fetchText(`${p.scheme}://${p.netloc}${m[1]}.json`);
        if (j.status === 200 && j.type.includes("json")) {
          const data = parseShopifyProduct(JSON.parse(j.text));
          if (data.created_ts) {
            Object.assign(info, data);
            info.platform = info.platform || "shopify";
            info.date_source = "api";
          }
        }
      } catch {}
    }
    if (!info.created_ts) [info.created_ts, info.date_source] = datesFromHtml(html);
    if (!info.title) {
      const t = TITLE_RE.exec(html);
      info.title = t ? Array.from(t[1].trim()).slice(0, 200).join("") : null;
    }
    if (!info.price) info.price = priceFromHtml(html);
  } catch (e) {   // mạng lỗi, shop chặn bot... ghi lại rồi bỏ qua
    info.error = String(e && e.message || e).slice(0, 300);
  }
  return info;
}
