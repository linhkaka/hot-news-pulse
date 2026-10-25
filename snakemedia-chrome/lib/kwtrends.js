// Gợi ý từ khoá từ xu hướng (giống snakepod/kwtrends.py): Google Trends (tìm kiếm thịnh hành, đọc RSS công khai)
// và Pinterest Trends (mở trang trends.pinterest.com trong cửa sổ quét, đọc dữ liệu JSON của trang — thử nghiệm).
//
// Kết quả lưu trong setting "kwtrends" = {nguồn: {thị trường: {ts, items}}}.
// Mỗi mục: term (từ khoá), score (độ lớn để xếp), growth (% tăng, Pinterest), info (ghi chú ngắn), group (danh mục).
export const SOURCES = {pinterest: "Pinterest Trends", google: "Google Trends"};

const ENT = {amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", "#39": "'"};
const unescape = s => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+|#39);/gi, (m, e) => e[0] === "#" && e !== "#39"
  ? String.fromCodePoint(e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : +e.slice(1)) : ENT[e.toLowerCase()] ?? m);

function tag(block, name) {
  const m = new RegExp(`<${name}>([\\s\\S]*?)</${name}>`).exec(block);
  if (!m) return null;
  let v = m[1].trim();
  if (v.startsWith("<![CDATA[")) v = v.slice(9, -3);
  return unescape(v).trim();
}

// '20,000+' / '2K+' / '1M+' -> số
function traffic(s) {
  const m = /^([0-9][0-9.,]*)\s*([KkMm]?)/.exec((s || "").trim());
  if (!m) return 0;
  return Math.trunc(parseFloat(m[1].replace(/,/g, "")) * ({k: 1e3, m: 1e6}[m[2].toLowerCase()] || 1));
}

export function parseGoogleRss(xml) {
  const out = [];
  for (const [, block] of (xml || "").matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const term = tag(block, "title");
    if (!term) continue;
    const t = tag(block, "ht:approx_traffic"), news = tag(block, "ht:news_item_title");
    out.push({term: term.toLowerCase(), score: traffic(t), growth: null,
      info: [t ? `${t} lượt tìm` : null, news].filter(Boolean).join(" · ").slice(0, 200), group: null});
  }
  return out;
}

const TERM_KEYS = ["term", "keyword", "query", "display_term", "search_term"];
const GROUP_KEYS = ["category", "category_name", "interest", "vertical", "group"];

function growth(d) {
  for (const [k, v] of Object.entries(d)) {
    const kl = k.toLowerCase();
    if (typeof v === "number" && (kl.includes("growth") || kl.includes("pct") || ["wow", "mom", "yoy"].includes(kl))) return v;
  }
  return null;
}

// Làm tròn kiểu Python (về số chẵn gần nhất khi đúng .5) để khớp với bản app
function pyRound(x) {
  const f = Math.floor(x), d = x - f;
  return d > 0.5 ? f + 1 : d < 0.5 ? f : (f % 2 === 0 ? f : f + 1);
}

function walk(x, group, out) {
  if (Array.isArray(x)) { for (const v of x) walk(v, group, out); return; }
  if (!x || typeof x !== "object") return;
  const g = GROUP_KEYS.map(k => x[k]).find(v => typeof v === "string") ?? group;
  const term = TERM_KEYS.map(k => x[k]).find(v => typeof v === "string" && v.trim());
  const gv = growth(x);
  if (term && gv !== null) {
    // Pinterest trả % tăng dạng 0.52 hoặc 52 tuỳ chỗ: < 20 coi như tỉ lệ
    const pct = Math.abs(gv) < 20 ? pyRound(gv * 100) : pyRound(gv);
    out.push({term: term.trim().toLowerCase(), score: pct, growth: pct, info: null, group: g ?? null});
  }
  for (const v of Object.values(x)) walk(v, g, out);
}

// Đọc lỏng phản hồi JSON của Pinterest Trends: mọi object có từ khoá + trường % tăng trưởng.
export function parsePinterestText(text) {
  let data;
  try { data = JSON.parse(text); } catch { return []; }
  const out = [];
  walk(data, null, out);
  return out;
}

// Bỏ trùng theo từ khoá, giữ điểm cao nhất, xếp giảm dần.
export function merge(items) {
  const best = new Map();
  for (const it of items) {
    const b = best.get(it.term);
    if (it.term && (!b || (it.score || 0) > (b.score || 0))) best.set(it.term, it);
  }
  return [...best.values()].sort((a, b) => (b.score || 0) - (a.score || 0) || (a.term < b.term ? -1 : a.term > b.term ? 1 : 0));
}

export async function save(db, source, market, items, now = null) {
  const data = await db.getSetting("kwtrends", {});
  (data[source] ||= {})[market] = {ts: now ?? db.now(), items: merge(items).slice(0, 200)};
  await db.setSetting("kwtrends", data);
}
