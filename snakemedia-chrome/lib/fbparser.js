// Đọc QC từ dữ liệu JSON mà trang Thư viện quảng cáo Facebook tải về (giống snakepod/fb_parser.py).
//
// Facebook đổi cấu trúc thường xuyên, nên thay vì bám theo đường dẫn cố định, ta duyệt toàn bộ
// cây JSON và lấy mọi object có "ad_archive_id" + "snapshot".

const isObj = v => v !== null && typeof v === "object" && !Array.isArray(v);

function* walk(obj) {
  const stack = [obj];
  while (stack.length) {
    const cur = stack.pop();
    if (isObj(cur)) {
      if ("ad_archive_id" in cur && isObj(cur.snapshot)) yield cur;
      stack.push(...Object.values(cur));
    } else if (Array.isArray(cur)) {
      stack.push(...cur);
    }
  }
}

// Số nguyên quá lớn (ID 16+ chữ số) mất chính xác trong JavaScript -> đổi thành chuỗi trước khi đọc
const BIG_INT = /([:,[]\s*)(-?\d{16,})(?=\s*[,}\]])/g;
const parseJSON = text => JSON.parse(text.replace(BIG_INT, '$1"$2"'));

// Phản hồi GraphQL có thể có tiền tố 'for (;;);' và nhiều JSON nối nhau theo dòng.
export function* loadsMany(text) {
  text = String(text || "").trim();
  if (text.startsWith("for (;;);")) text = text.slice("for (;;);".length);
  try {
    yield parseJSON(text);
    return;
  } catch {}
  for (let line of text.split(/\r\n|\r|\n/)) {
    line = line.trim();
    if (line.startsWith("{") || line.startsWith("[")) {
      try { yield parseJSON(line); } catch {}
    }
  }
}

function textOf(v) {
  if (isObj(v)) v = v.text;
  if (typeof v !== "string") return null;
  v = v.trim();
  if (!v || v.includes("{{")) return null;   // QC động (DCO) chứa biến kiểu {{product.name}}
  return v;
}

// scheme://netloc/path?query#frag  (tách như urllib.parse.urlparse, không chuẩn hoá đường dẫn)
export function urlparse(url) {
  const m = /^([a-zA-Z][a-zA-Z0-9+.-]*):\/\/([^/?#]*)([^?#]*)(?:\?([^#]*))?/.exec(url || "");
  if (!m) return {scheme: "", netloc: "", path: "", query: ""};
  return {scheme: m[1].toLowerCase(), netloc: m[2], path: m[3], query: m[4] || ""};
}

function unwrapLink(url) {
  // Link qua l.facebook.com/l.php?u=... -> link thật
  if (!url) return null;
  const p = urlparse(url);
  if (p.netloc.endsWith("facebook.com") && p.path.startsWith("/l.php")) {
    const u = new URLSearchParams(p.query).get("u");
    if (u) { try { return decodeURIComponent(u); } catch { return u; } }
  }
  return url;
}

// Bỏ tham số tracking, giữ scheme+domain+path để gom các QC cùng trang bán.
export function cleanUrl(url) {
  url = unwrapLink(url);
  if (!url || !url.startsWith("http")) return [null, null];
  const p = urlparse(url);
  const netloc = p.netloc.toLowerCase();
  const domain = netloc.startsWith("www.") ? netloc.slice(4) : netloc;
  const path = p.path.replace(/\/+$/, "");
  return [`${p.scheme}://${netloc}${path}`, domain];
}

export function normalize(node) {
  const snap = node.snapshot;
  const cards = snap.cards || [];
  const videos = [...(snap.videos || []), ...cards.filter(c => c.video_preview_image_url)];
  const images = [...(snap.images || []), ...cards.filter(c => c.resized_image_url)];

  let videoUrl = null, thumbUrl = null;
  if (videos.length) {
    const v = videos[0];
    videoUrl = v.video_hd_url || v.video_sd_url || null;
    thumbUrl = v.video_preview_image_url || null;
  } else if (images.length) {
    const i = images[0];
    thumbUrl = i.resized_image_url || i.original_image_url || null;
  }

  const link = snap.link_url || (cards.find(c => c.link_url) || {}).link_url || null;
  const [linkUrl, domain] = cleanUrl(link);
  const firstText = k => textOf(snap[k]) || cards.map(c => textOf(c[k])).find(Boolean) || null;

  return {
    ad_id: String(node.ad_archive_id),
    collation_id: node.collation_id ? String(node.collation_id) : null,
    collation_count: parseInt(node.collation_count || 1, 10) || 1,
    page_id: String(node.page_id || snap.page_id || ""),
    page_name: node.page_name || snap.page_name || null,
    start_ts: node.start_date ?? null,
    end_ts: node.end_date ?? null,
    is_active: node.is_active ? 1 : 0,
    title: firstText("title"),
    body: firstText("body"),
    link_url: linkUrl,
    domain,
    thumb_url: thumbUrl,
    video_url: videoUrl,
    has_video: videos.length > 0,
  };
}

export function parseJsonText(text) {
  const ads = new Map();
  for (const blob of loadsMany(text)) for (const node of walk(blob)) {
    const ad = normalize(node);
    ads.set(ad.ad_id, ad);
  }
  return [...ads.values()];
}

const SCRIPT_RE = /<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g;

export function parseHtml(html) {
  const ads = new Map();
  for (const m of String(html || "").matchAll(SCRIPT_RE)) {
    if (!m[1].includes("ad_archive_id")) continue;
    for (const ad of parseJsonText(m[1])) ads.set(ad.ad_id, ad);
  }
  return [...ads.values()];
}
