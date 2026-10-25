// Giao diện SNAKEMEDIA POD — 1 file dùng chung cho bản app (snakepod/static/app.js, API qua fetch)
// và bản tiện ích Chrome (dashboard.js, API chạy trong phần nền, gọi qua chrome.runtime). Sửa ở app rồi chạy
// snakemedia-chrome/sync_ui.py để chép sang tiện ích.
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const IS_EXT = !!(globalThis.chrome && chrome.runtime && chrome.runtime.id);
const NOUN = IS_EXT ? "Tiện ích" : "Tool";
const CONFIG_FILE = IS_EXT ? "lib/config.js" : "snakepod/config.py";
const api = async (p, o = {}) => {
  if (!IS_EXT) return fetch(p, o).then(async r => {
    if (!r.ok) { let m = r.status; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
    return r.json();
  });
  const r = await chrome.runtime.sendMessage({type: "api", method: o.method || "GET", path: p,
    body: o.body ? JSON.parse(o.body) : null});
  if (!r) throw new Error("Không kết nối được phần nền của tiện ích. Tải lại trang này.");
  if (!r.ok) throw new Error(r.detail || r.status);
  return r.data;
};
const post = (p, body) => api(p, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
const del = p => api(p, {method: "DELETE"});
const days = d => d == null ? "?" : `${Math.round(d)} ngày`;
const fmtDate = ts => ts ? new Date(ts * 1000).toISOString().slice(0, 10) : "?";
const ago = ts => { if (!ts) return "chưa"; const s = Date.now() / 1000 - ts;
  return s < 3600 ? `${Math.max(1, Math.round(s / 60))} phút trước` : s < 86400 ? `${Math.round(s / 3600)} giờ trước` : `${Math.round(s / 86400)} ngày trước`; };
const thumb = v => v.thumb_src || (v.thumb && !IS_EXT ? `/thumbs/${encodeURIComponent(v.thumb)}` : v.thumb_url) || "";
const enc = encodeURIComponent;
// Nút bấm mang dữ liệu trong data-args (JSON) thay vì nhúng vào mã JS: tên page/shop có dấu nháy cũng an toàn
const act = (name, ...args) => `data-act="${name}" data-args="${esc(JSON.stringify(args))}"`;
const LABEL = {sap_win: ["Sắp WIN", "p"], win: ["Video Win", "g"], scale: ["Video scale", ""], theo_doi: ["Chờ thêm dữ liệu", ""],
  trang_cu: ["Trang bán cũ", "r"], cu: ["Video già", "r"]};
const TABS = ["potential", "cow", "test", "hidden", "dig"];   // danh sách video lọc theo tab (không theo nhãn)
const TITLES = {shopify: "Kết nối Shopify", trends: "Xu hướng thị trường", potential: "Video Tiềm Năng", cow: "SP bò sữa", test: "Video test", hidden: "Đã ẩn", dig: "Đào sâu",
  stores: "Quét store win", history: "Lịch sử quét", data: "Góp kho dữ liệu", notify: "Thông báo", safety: "Chế độ an toàn", viral: "Video viral", spread: "QC Facebook đang lan nhanh", overview: "Tổng quan", scan: "Quét từ khoá", all: "Tất cả video", niches: "Niche POD",
  follows: "Theo dõi đặc biệt", keywords: "Tự quét mỗi đêm", shops: "Kho shop"};
const DATE_SOURCE = {api: "dữ liệu sản phẩm", uuid: "ước tính từ mã sản phẩm", anh: "ước tính từ ảnh sản phẩm"};
const POD_KEYWORDS = ["personalized dog shirt", "custom name mug", "personalized ornament", "nurse shirt", "teacher mug",
  "grandma sweatshirt", "memorial canvas", "custom pet portrait", "fishing shirt", "veteran flag", "halloween doormat",
  "christmas blanket"];

let view = location.hash.slice(1) || "overview", openCid = null, openVid = null;
const viralFilters = {platform: "", label: "", sort: "vph", market: ""};
const VLABEL = {dang_no: ["Đang nổ", "r"], viral: ["Viral", "p"], dang_len: ["Đang lên", "g"], binh_thuong: ["Bình thường", ""],
  top_ads: ["Top Ads", "o"], xu_huong: ["Thịnh hành", "o"]};
const SORTS = {vph: "Xếp: xem/giờ", views: "Xếp: lượt xem", likes: "Xếp: lượt thích", engagement: "Xếp: tương tác",
  new: "Xếp: mới nhất"};
const PLATFORM = {tiktok: "TikTok", tiktok_ads: "TikTok Top Ads", tiktok_trend: "TikTok thịnh hành", fb_reels: "Facebook Reels"};
// Thị trường + nguồn chọn được thị trường (lấy 1 lần từ máy chủ / phần nền)
let marketsP = null;
const getMarkets = () => (marketsP ||= api("/api/markets"));
const num = n => n == null ? "?" : n >= 1e9 ? (n / 1e9).toFixed(1) + "B" : n >= 1e6 ? (n / 1e6).toFixed(1) + "M"
  : n >= 1e3 ? (n / 1e3).toFixed(1) + "K" : String(n);
const cover = v => v.cover_src || (v.cover_path && !IS_EXT ? `/thumbs/${encodeURIComponent(v.cover_path)}` : v.cover_url) || "";
// Bộ lọc dùng chung cho các màn hình danh sách video
const filters = {product_type: "", niche: "", pod: false, page_id: "", shop: "", product: "", scopeName: ""};

// Kiểu xem (danh sách / lưới) nhớ trong trình duyệt; trang hiện tại về 0 mỗi khi đổi mục hoặc bộ lọc
let layout = "list", pageOffset = 0;
try { layout = localStorage.getItem("snakepod.layout") || "list"; } catch {}
const PAGE = 60;
function setLayout(l) { layout = l; try { localStorage.setItem("snakepod.layout", l); } catch {} render(); }
function goPage(off) { pageOffset = Math.max(0, off); render(); window.scrollTo(0, 0); }

function setView(v) { if (v !== view) closeDrawer(); view = v; pageOffset = 0; location.hash = v; render(); }
document.querySelectorAll("#nav a").forEach(a => a.onclick = () => { clearScope(false); setView(a.dataset.view); });
window.onhashchange = () => { const v = location.hash.slice(1); if (v && v !== view) { closeDrawer(); view = v; pageOffset = 0; render(); } };
let t; $("#search").oninput = () => { clearTimeout(t); t = setTimeout(() => { pageOffset = 0; render(); }, 250); };

function clearScope(rerender = true) { filters.page_id = filters.shop = filters.product = filters.scopeName = ""; pageOffset = 0; if (rerender) render(); }
function showScope(kind, key, name) {
  filters.page_id = kind === "page" ? key : ""; filters.shop = kind === "shop" ? key : "";
  filters.scopeName = name || key; setView("all");
}
const isList = v => !!LABEL[v] || v === "all" || TABS.includes(v);
function filterBy(key, value) { filters[key] = value; pageOffset = 0; if (!isList(view)) setView("all"); else render(); }

async function refreshCounts() {
  const s = await api("/api/stats");
  for (const l of s.labels) document.querySelector(`[data-count=${l.key}]`).textContent = l.count;
  document.querySelector("[data-count=all]").textContent = s.total;
  for (const [k, n] of Object.entries(s.tabs || {})) { const el = document.querySelector(`[data-tab=${k}]`); if (el) el.textContent = n || ""; }
  api("/api/autoscan").then(a => { $("#cnt-follows").textContent = a.follows; $("#cnt-keywords").textContent = a.keywords; });
  return s;
}

function tabChips(v) {
  let h = "";
  if (v.potential && view !== "potential") h += `<span class="chip g">🌱 Tiềm năng</span>`;
  if (v.cash_cow && view !== "cow") h += `<span class="chip o">🐄 Bò sữa</span>`;
  if ((v.marks || []).includes("test") && view !== "test") h += `<span class="chip p">🧪 Test</span>`;
  return h;
}

function podChips(v) {
  let h = "";
  if (v.product_type) h += `<span class="chip o">${esc(v.product_type)}</span>`;
  if (v.personalized) h += `<span class="chip p">cá nhân hoá</span>`;
  return h;
}

function meta(v) {
  const parts = [];
  if (v.price) parts.push(`$${esc(v.price)}`);
  if (view === "spread") parts.push(`<b class="green">+${v.ads_new_48h} QC · +${v.shops_new_48h} shop mới / 48h</b>`);
  parts.push(`video ${days(v.video_age_days)}`);
  if (v.landing_age_days != null) parts.push(`<span class="${v.page_old ? "red" : ""}">URL ${days(v.landing_age_days)}${v.landing_date_source && v.landing_date_source !== "api" ? "*" : ""}</span>`);
  parts.push(`${v.pages_active}/${v.pages_total} page`, `${v.shops_active}/${v.shops_total} shop`, `${v.ads_per_day} QC/ngày`);
  return parts.join(" · ") + podChips(v) + tabChips(v) + (v.platform ? `<span class="chip">${esc(v.platform)}</span>` : "");
}

function row(v) {
  const img = thumb(v) ? `<img loading="lazy" src="${esc(thumb(v))}">` : `<div class="ph"></div>`;
  const [ln, cls] = LABEL[v.label] || [v.label, ""];
  return `<div class="row ${v.cid === openCid ? "on" : ""}" data-cid="${esc(v.cid)}">${img}
    <div style="min-width:0"><div class="t">${esc(v.title)}</div>
    <div class="m">${meta(v)}${view === "all" ? `<span class="chip ${cls}">${ln}</span>` : ""}</div>
    ${v.niches && v.niches.length ? `<div class="m">🎯 ${v.niches.map(esc).join(", ")}</div>` : ""}</div></div>`;
}

function filterBar(facets) {
  const opt = (list, cur) => list.map(x => `<option value="${esc(x.name)}" ${x.name === cur ? "selected" : ""}>${esc(x.name)} (${x.count})</option>`).join("");
  return `<div class="filters">
    ${filters.scopeName ? `<span class="scope">Đang xem: <b>${esc(filters.scopeName)}</b><a ${act("clearScope")}>✕ bỏ</a></span>` : ""}
    <select data-change="product_type"><option value="">Mọi loại sản phẩm</option>${opt(facets.product_types, filters.product_type)}</select>
    <select data-change="niche"><option value="">Mọi niche</option>${opt(facets.niches, filters.niche)}</select>
    <label><input type="checkbox" ${filters.pod ? "checked" : ""} data-change="pod"> Chỉ POD</label>
    ${layoutToggle(true)}
  </div>`;
}

function layoutToggle(withTable = false) {
  const b = (k, name) => `<button class="small ${layout === k ? "on" : ""}" ${act("setLayout", k)}>${name}</button>`;
  return `<span class="seg" style="margin-left:auto">${b("list", "☰ Danh sách")}${b("grid", "▦ Lưới")}${withTable ? b("table", "▤ Bảng") : ""}</span>`;
}

const dm = ts => ts ? new Date(ts * 1000).toLocaleDateString("vi-VN", {day: "2-digit", month: "2-digit"}) : "?";
const plus = (n, unit = "") => n > 0 ? `<b class="green">+${n}</b>${unit}` : n < 0 ? `<b class="red">${n}</b>${unit}` : `+0${unit}`;

// Bảng số liệu: mỗi cột 1 số lớn + 1 dòng giải thích nhỏ
function fbTable(items) {
  const cell = (big, small, cls = "") => `<td class="num"><b class="${cls}" style="font-size:15px">${big}</b><br><small class="note">${small}</small></td>`;
  return `<div class="list"><table class="vt"><tr><th>Video</th><th class="num">Ads cũ</th><th class="num">Win</th><th class="num">Scale</th>
    <th class="num">Tuổi video</th><th class="num">Tuổi URL</th><th class="num">Shop</th><th class="num">Fanpage</th></tr>
    ${items.map(v => {
      const b = v.buckets, d = v.delta;
      const before = v.page_old && v.first_ts && v.landing_created_ts ? Math.round((v.first_ts - v.landing_created_ts) / 86400) : null;
      return `<tr class="vrow ${v.cid === openCid ? "on" : ""}" data-cid="${esc(v.cid)}">
        <td><div class="vcell">${thumb(v) ? `<img loading="lazy" src="${esc(thumb(v))}">` : `<div class="ph"></div>`}
          <div style="min-width:0"><div class="t">${esc(v.title)}</div>
          <div class="m">${v.price ? "$" + esc(v.price) + " · " : ""}${v.ads_per_day} ads/ngày${podChips(v)}${tabChips(v)}</div></div></div></td>
        ${cell(b.old + " ads", `lâu nhất ${Math.round(v.longest_run_days || 0)} ngày`)}
        ${cell(b.win, `${v.shops_win} shop giữ`, "green")}
        ${cell(b.scale, d ? plus(d.scale, " ads hôm nay") : `${v.ads_new_24h} QC mới 24h`)}
        ${cell(days(v.video_age_days), `lên ${dm(v.first_ts)}`)}
        ${cell(v.landing_age_days == null ? "—" : days(v.landing_age_days) + (v.landing_date_source && v.landing_date_source !== "api" ? "*" : ""),
          before ? `trước video ${before} ngày` : v.landing_created_ts ? `tạo ${dm(v.landing_created_ts)}` : "chưa rõ", v.page_old ? "red" : "")}
        ${cell(`${v.shops_active}/${v.shops_total}`, `${v.shops_new_post} đang lên bài`)}
        ${cell(`${v.pages_active}/${v.pages_total}`, d ? plus(d.pages_active, " fanpage hôm nay") : "")}
      </tr>`;
    }).join("")}</table></div>`;
}

function pager(total) {
  if (total <= PAGE) return total ? `<div class="pager note">${total} video</div>` : "";
  const pages = Math.ceil(total / PAGE), cur = Math.floor(pageOffset / PAGE) + 1;
  return `<div class="pager"><button class="small" ${cur > 1 ? act("goPage", pageOffset - PAGE) : "disabled"}>← Trước</button>
    <span class="note">Trang ${cur} / ${pages} · ${total} video</span>
    <button class="small" ${cur < pages ? act("goPage", pageOffset + PAGE) : "disabled"}>Sau →</button></div>`;
}

// Ô lưới: ảnh lớn, rê chuột để xem trước video (nếu link video còn hạn)
function gridCard(attrs, img, video, chip, title, meta) {
  return `<div class="gcard" ${attrs} ${video ? `data-video="${esc(video)}"` : ""}>
    <div class="gimg">${img ? `<img loading="lazy" src="${esc(img)}">` : ""}${chip}${video ? `<span class="play">▶</span>` : ""}</div>
    <div class="gbody"><div class="gt">${esc(title)}</div><div class="m">${meta}</div></div></div>`;
}

// Vòng tuổi video: càng mới vòng càng đầy (30 ngày = rỗng); xanh ≤ 3 ngày, cam ≤ 14 ngày, đỏ già hơn
function ageRing(d) {
  const n = d == null ? "?" : Math.round(d);
  const fill = d == null ? 0 : Math.max(0.05, 1 - Math.min(d, 30) / 30);
  const cls = d == null ? "" : d <= 3 ? "g" : d <= 14 ? "o" : "r";
  return `<div class="ring ${cls}" style="--p:${fill.toFixed(2)}"><b>${n}</b><small>ngày</small></div>`;
}

// Thẻ video kiểu lưới: tuổi video, tuổi trang bán, lý do có trong kho, Win / Scale / Shop / Fanpage, nút Clone + Phân tích
function fbCard(v, i = 0) {
  const [ln, cls] = LABEL[v.label] || [v.label, ""];
  const b = v.buckets || {win: 0, scale: 0};
  const before = v.page_old && v.first_ts && v.landing_created_ts ? Math.round((v.first_ts - v.landing_created_ts) / 86400) : null;
  const shop = v.landing_age_days == null ? `<div class="note">Trang bán chưa rõ tuổi</div>`
    : `<div class="note ${before ? "red" : ""}">Trang bán ${days(v.landing_age_days)}${v.landing_date_source && v.landing_date_source !== "api" ? "*" : ""}${before ? ` · cũ hơn video ${before} ngày` : ""}</div>`;
  const kws = (v.keywords || []).filter(k => k !== "demo");
  const why = kws.length ? `Vì bạn tìm "${esc(kws[0])}"${kws.length > 1 ? ` +${kws.length - 1}` : ""}`
    : (v.keywords || []).length ? "Dữ liệu mẫu" : "Từ đào sâu / soi store / theo dõi";
  const stat = (n, name, c = "") => `<div><b class="${c}">${n}</b><small>${name}</small></div>`;
  const chips = (v.potential && v.label !== "sap_win" ? `<span class="chip g gchip">🌱 Tiềm năng</span>` : `<span class="chip ${cls} gchip">${ln}</span>`)
    + `<span class="rank">#${pageOffset + i + 1}</span>`;
  return `<div class="gcard vcard" data-cid="${esc(v.cid)}" ${v.video_url ? `data-video="${esc(v.video_url)}"` : ""}>
    <div class="gimg">${thumb(v) ? `<img loading="lazy" src="${esc(thumb(v))}">` : ""}${chips}${v.video_url ? `<span class="play">▶</span>` : ""}</div>
    <div class="gbody">
      <div class="age">${ageRing(v.video_age_days)}<div><b>Video đăng ${dm(v.first_ts)}</b>${shop}</div></div>
      <div class="why">${why}</div>
      <div class="gt">${esc(v.title)}</div>
      <div class="note dom">${esc(v.domain || (v.shops || [])[0] || "")}${v.price ? " · $" + esc(v.price) : ""}</div>
      <div class="stats">${stat(b.win, "Win", "green")}${stat(b.scale, "Scale")}${stat(`${v.shops_active}<small>/${v.shops_total}</small>`, "Shop")}${stat(v.pages_active, "Fanpage")}</div>
      <div class="cbtns">${v.clone ? `<a class="btn small" target="_blank" rel="noopener" href="${esc(v.clone.admin_url)}" title="Đã clone ${ago(v.clone.ts)}">✓ Đã clone</a>`
        : `<button class="small primary" ${act("cloneVideo", v.cid)}>⧉ Clone</button>`}
        <button class="small" ${act("openDrawer", v.cid)}>📊 Phân tích</button></div>
    </div></div>`;
}

function wrapItems(items, rowFn, cardFn, tableFn = null, lay = layout) {
  if (lay === "table" && tableFn) return tableFn(items);
  return lay === "grid" ? `<div class="grid">${items.map(cardFn).join("")}</div>`
    : `<div class="list">${items.map(rowFn).join("")}</div>`;
}

const TAB_NOTES = {
  potential: `Video vừa nhú: ≤ 10 ngày tuổi, đã có ≥ 2 QC mới trong 48 giờ hoặc ≥ 2 page chạy, nhưng chưa đủ điều kiện Sắp WIN.
    Hợp với người chạy TikTok: bắt con đang nhú trước khi nó tràn khắp nơi.`,
  cow: `Sản phẩm chạy đều nhiều tuần, không bùng lên rồi tắt: video ≥ 30 ngày, có QC sống ≥ 21 ngày, ≥ 5 QC sống trên 14 ngày,
    ≥ 3 shop đang chạy. Hợp với Google Shopping / Search, SEO, sàn, free traffic — kênh cần thời gian mới lên top nên hàng phải sống dai.`,
  test: "Video bạn đánh dấu để test (nút + Video test trong bảng chi tiết).",
  hidden: "Video bạn đã ẩn khỏi mọi danh sách. Mở chi tiết → Bỏ ẩn để đưa lại.",
  dig: `Video Sắp WIN / Tiềm năng chưa đào (hoặc đào đã quá 7 ngày). Đào sâu = soi toàn bộ QC (cả QC đã tắt) của các page
    đang chạy video để tìm mốc chạy sớm nhất và mọi shop đang bán.`,
};

async function renderList(label, extra = {}) {
  const p = new URLSearchParams(extra);
  const q = $("#search").value.trim();
  if (label) p.set("label", label);
  if (q) p.set("q", q);
  for (const k of ["product_type", "niche", "page_id", "shop", "product"]) if (filters[k]) p.set(k, filters[k]);
  if (filters.pod) p.set("pod", "true");
  p.set("offset", pageOffset); p.set("limit", PAGE);
  const {items, facets, total} = await api("/api/videos?" + p);
  const bar = filterBar(facets);
  if (extra.spread) $("#cnt-spread").textContent = total;
  let note = extra.spread ? `<p class="note">Video có ≥ 5 QC mới hoặc ≥ 2 shop mới chép trong 48 giờ qua (sửa trong ${CONFIG_FILE}). Đây là dấu hiệu một video đang được nhiều người đổ tiền cùng lúc.</p>` : "";
  if (extra.tab) note = `<p class="note">${TAB_NOTES[extra.tab]}</p>`;
  if (extra.tab === "dig" && total) note += `<div class="toolbar"><input id="digN" type="number" min="1" max="50" value="${Math.min(5, total)}" style="width:70px">
    <button class="primary small" ${act("digBatch")}>⤓ Đào các video đầu danh sách</button>
    <span class="note">Mỗi video soi tối đa 6 page, nghỉ 20–45 giây giữa 2 page (chế độ an toàn).</span></div>`;
  if (!items.length) return note + bar + `<div class="list"><div class="empty">Chưa có video nào ở mục này.<br>Vào <a ${act("setView", "scan")}><b>Quét từ khoá</b></a> để bắt đầu.</div></div>`;
  // SP bò sữa mặc định xem dạng bảng
  const lay = extra.tab === "cow" && layout === "list" ? "table" : layout;
  pageItems = {cids: items.map(v => v.cid), vids: []};
  return note + bar + mediaBar(items.length) + wrapItems(items, row, fbCard, fbTable, lay) + pager(total);
}

// ---------------- tải ảnh / video ----------------

let pageItems = {cids: [], vids: []};   // video đang hiện trên trang (để tải cả trang)

function mediaBar(n) {
  return `<div class="toolbar mediabar"><span class="note">Tải ${n} video đang xem:</span>
    <button class="small" ${act("batchMedia", "video")}>⬇ Video</button>
    <button class="small" ${act("batchMedia", "image")}>🖼 Ảnh</button>
    <button class="small" ${act("batchMedia", "both")}>⬇ Cả hai</button>
    <span class="note">— lưu vào thư mục ${IS_EXT ? "Tải về (Downloads)/SnakemediaPOD" : "Downloads\\SnakemediaPOD"}</span></div>`;
}

function saveBlob(name, blob) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), {href: url, download: name});
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

// kind: ad (1 QC) | video (video QC) | social (video viral); type: video | image
async function downloadMedia(kind, key, type) {
  const path = `/api/media/${kind}/${enc(key)}?type=${type}`;
  try {
    if (IS_EXT) { await api(path); return; }          // tiện ích: Chrome tự tải về thư mục Tải về
    const r = await fetch(path);
    if (!r.ok) { let m = r.status; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
    const name = (/filename="([^"]+)"/.exec(r.headers.get("content-disposition") || "") || [])[1] || "media";
    saveBlob(name, await r.blob());
  } catch (e) { alert("Không tải được: " + e.message); }
}

async function batchMedia(kind) {
  if (!pageItems.cids.length && !pageItems.vids.length) return alert("Trang này chưa có video nào");
  try {
    const r = await post("/api/media/batch", {...pageItems, kind});
    pollJobs();
    alert(`Đang tải ${pageItems.cids.length + pageItems.vids.length} video vào ${IS_EXT ? "thư mục Tải về/SnakemediaPOD" : r.folder}. Xem tiến độ ở Nhật ký.`);
  } catch (e) { alert(e.message); }
}

const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleString("vi-VN", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"}) : "?";

// ---------------- Video viral ----------------

function socialMeta(v) {
  const parts = [`<span class="chip">${esc(PLATFORM[v.platform] || v.platform)}</span>`];
  if (v.platform === "tiktok_trend") {
    if (v.duration) parts.push(`${v.duration} giây`);
  } else if (v.platform === "tiktok_ads") {
    if (v.likes != null) parts.push(`❤ ${num(v.likes)}`);
    if (v.extra.ctr != null) parts.push(`CTR ${esc(v.extra.ctr)}`);
    if (v.extra.cost != null) parts.push(`ngân sách mức ${esc(v.extra.cost)}`);
    if (v.extra.industry_key) parts.push(esc(v.extra.industry_key));
  } else {
    parts.push(`<b>${num(v.views)}</b> xem`, `<b>${num(v.vph)}</b>/giờ${v.recent_vph != null ? " (thật)" : ""}`,
      `${days(v.age_days)}`);
    if (v.engagement != null) parts.push(`tương tác ${v.engagement}%`);
    if (v.share_rate != null) parts.push(`chia sẻ ${v.share_rate}%`);
  }
  if (v.author) parts.push("@" + esc(v.author));
  return parts.join(" · ") + podChips(v) + (v.market ? `<span class="chip">🌍 ${esc(v.market)}</span>` : "");
}

function socialRow(v) {
  const img = cover(v) ? `<img loading="lazy" src="${esc(cover(v))}">` : `<div class="ph"></div>`;
  const [ln, cls] = VLABEL[v.label] || [v.label, ""];
  return `<div class="row ${v.vid === openVid ? "on" : ""}" data-vid="${esc(v.vid)}">${img}
    <div style="min-width:0"><div class="t"><span class="chip ${cls}" style="margin:0 6px 0 0">${ln}</span>${esc(v.caption || "(không có mô tả)")}</div>
    <div class="m">${socialMeta(v)}</div>
    ${v.niches && v.niches.length ? `<div class="m">🎯 ${v.niches.map(esc).join(", ")}</div>` : ""}</div></div>`;
}

async function renderViral() {
  const p = new URLSearchParams({sort: viralFilters.sort});
  const q = $("#search").value.trim();
  if (q) p.set("q", q);
  for (const k of ["platform", "label", "market"]) if (viralFilters[k]) p.set(k, viralFilters[k]);
  for (const k of ["product_type", "niche"]) if (filters[k]) p.set(k, filters[k]);
  if (filters.pod) p.set("pod", "true");
  p.set("offset", pageOffset); p.set("limit", PAGE);
  const [res, kws, mk] = await Promise.all([api("/api/viral?" + p), api("/api/viral/keywords"), getMarkets()]);
  const {items, facets, counts, total} = res;
  $("#cnt-viral").textContent = (counts.dang_no || 0) + (counts.viral || 0);
  const opt = (obj, cur, all) => `<option value="">${all}</option>` + Object.entries(obj).map(([k, n]) =>
    `<option value="${k}" ${k === cur ? "selected" : ""}>${esc(n)}</option>`).join("");
  const fopt = (list, cur) => list.map(x => `<option value="${esc(x.name)}" ${x.name === cur ? "selected" : ""}>${esc(x.name)} (${x.count})</option>`).join("");
  const form = `<form class="card" id="viralForm" style="margin-bottom:12px">
      <div class="toolbar" style="margin:0 0 8px">
        <select name="platform"><option value="tiktok">TikTok tìm kiếm (từ khoá / #hashtag)</option>
          <option value="tiktok_trend">TikTok thịnh hành (theo thị trường)</option>
          <option value="tiktok_ads">TikTok Top Ads (theo thị trường)</option>
          <option value="fb_reels">Facebook Reels (thử nghiệm)</option></select>
        <input name="keywords" placeholder="Từ khoá / #hashtag, cách nhau bằng dấu phẩy — vd: dog mom, #nursesoftiktok" style="flex:1;min-width:260px">
        <select name="period" title="Khoảng thời gian (Creative Center)"><option value="7">7 ngày</option><option value="30">30 ngày</option><option value="120">120 ngày</option></select>
        <label class="note"><input type="checkbox" name="save" checked> Tự quét mỗi đêm</label>
        <button class="primary">Quét</button></div>
      <div class="chips markets">${Object.entries(mk.markets).map(([c, n]) =>
        `<label class="chip"><input type="checkbox" name="countries" value="${c}" ${c === "US" ? "checked" : ""}> ${c} · ${esc(n)}</label>`).join("")}</div>
      <p class="note" style="margin:6px 0 0"><b>Thị trường</b> chỉ áp dụng cho nguồn Creative Center (TikTok thịnh hành, Top Ads, hashtag xu hướng):
      mỗi thị trường = 1 lượt quét. TikTok tìm kiếm và Facebook Reels <b>không chọn được thị trường</b> — kết quả theo tài khoản + IP của bạn.
      Nguồn Creative Center có thể bỏ trống từ khoá (lấy toàn bộ danh sách thịnh hành).</p></form>
    <p class="note">${IS_EXT ? "Tiện ích dùng tài khoản TikTok / Facebook đang đăng nhập trên Chrome này (mục Chế độ an toàn → nút Đăng nhập)."
      : 'TikTok và Facebook Reels cần đăng nhập 1 lần (menu Start → "Đăng nhập TikTok" / "Đăng nhập Facebook").'}
    Mỗi lần quét lưu lại số liệu, nên từ lần quét thứ 2 ${NOUN.toLowerCase()} tính được <b>tốc độ tăng thật</b> (xem/giờ giữa 2 lần quét).</p>
    ${kws.length ? `<div class="chips">${kws.map(k => `<span class="chip">${esc(mk.sources[k.platform] || k.platform)}: ${esc(k.keyword || "tất cả")}${k.country ? " · " + esc(k.country) : ""}
      <a ${act("removeViralKw", k.platform, k.keyword, k.country)} title="Bỏ tự quét"> ✕</a></span>`).join("")}</div>` : ""}`;
  const labelChips = `<div class="chips">${Object.entries(VLABEL).map(([k, [n, c]]) =>
    `<span class="chip ${c}" ${act("viralFilter", "label", viralFilters.label === k ? "" : k)} style="${viralFilters.label === k ? "outline:2px solid currentColor" : ""}">${n} (${counts[k] || 0})</span>`).join("")}</div>`;
  const bar = `<div class="filters">
    <select data-change="viralPlatform">${opt(PLATFORM, viralFilters.platform, "Mọi nền tảng")}</select>
    <select data-change="viralMarket"><option value="">Mọi thị trường</option>${Object.entries(res.markets || {}).map(([m, n]) =>
      `<option value="${m}" ${m === viralFilters.market ? "selected" : ""}>${m} (${n})</option>`).join("")}</select>
    <select data-change="product_type"><option value="">Mọi loại sản phẩm</option>${fopt(facets.product_types, filters.product_type)}</select>
    <select data-change="niche"><option value="">Mọi niche</option>${fopt(facets.niches, filters.niche)}</select>
    <label><input type="checkbox" ${filters.pod ? "checked" : ""} data-change="pod"> Chỉ POD</label>
    <select data-change="viralSort">${Object.entries(SORTS).map(([k, n]) =>
      `<option value="${k}" ${k === viralFilters.sort ? "selected" : ""}>${n}</option>`).join("")}</select>
    ${layoutToggle()}
  </div>`;
  pageItems = {cids: [], vids: items.map(v => v.vid)};
  const list = items.length ? mediaBar(items.length) + wrapItems(items, socialRow, socialCard) + pager(total)
    : `<div class="list"><div class="empty">Chưa có video viral nào. Nhập từ khoá ở trên rồi bấm Quét.</div></div>`;
  return form + labelChips + bar + list;
}

function socialCard(v) {
  const [ln, cls] = VLABEL[v.label] || [v.label, ""];
  const meta = v.platform === "tiktok_ads"
    ? `${esc(PLATFORM[v.platform])} · ❤ ${num(v.likes)}${v.extra.ctr != null ? " · CTR " + esc(v.extra.ctr) : ""}`
    : `${esc(PLATFORM[v.platform])} · <b>${num(v.views)}</b> xem · <b>${num(v.vph)}</b>/giờ · ${days(v.age_days)}`;
  return gridCard(`data-vid="${esc(v.vid)}"`, cover(v), v.video_url, `<span class="chip ${cls} gchip">${ln}</span>`,
    v.caption || "(không có mô tả)", meta + podChips(v));
}

async function openSocial(vid) {
  openVid = vid; openCid = null;
  document.querySelectorAll(".row").forEach(r => r.classList.toggle("on", r.dataset.vid === vid));
  const v = await api(`/api/viral/${enc(vid)}`);
  const [ln, cls] = VLABEL[v.label] || [v.label, ""];
  const img = cover(v) ? `<img class="hero" src="${esc(cover(v))}">` : `<div class="hero"></div>`;
  const kv = (k, val) => `<div class="kv"><span>${k}</span><b>${val}</b></div>`;
  const ex = v.extra || {};
  $("#drawer").innerHTML = `<button class="x" ${act("closeDrawer")}>✕</button>${img}
    <h2>${esc(v.caption || "(không có mô tả)")}</h2>
    <div><span class="chip ${cls}">${ln}</span><span class="chip">${esc(PLATFORM[v.platform])}</span>${podChips(v)}
      <span class="note"> · ${v.author ? "@" + esc(v.author) + " · " : ""}quét ${ago(v.last_seen)}</span></div>
    <div class="btns">
      <a class="btn primary" target="_blank" rel="noopener" href="${esc(v.url)}">▶ Mở video</a>
      ${v.video_url ? `<button ${act("downloadMedia", "social", v.vid, "video")}>⬇ Tải video</button>` : `<span></span>`}
      <button ${act("downloadMedia", "social", v.vid, "image")}>🖼 Tải ảnh bìa</button>
    </div>
    ${v.market ? `<div class="kv"><span>Thị trường</span><b>🌍 ${esc(v.market)}</b></div>` : ""}
    <h3>Số liệu</h3>
    ${v.platform === "tiktok_ads" ? kv("Lượt thích", num(v.likes)) + (ex.ctr != null ? kv("CTR", esc(ex.ctr)) : "")
        + (ex.cost != null ? kv("Mức ngân sách", esc(ex.cost)) : "") + (ex.brand_name ? kv("Thương hiệu", esc(ex.brand_name)) : "")
        + (ex.industry_key ? kv("Ngành", esc(ex.industry_key)) : "") + (ex.objective_key ? kv("Mục tiêu QC", esc(ex.objective_key)) : "")
      : kv("Lượt xem", num(v.views)) + kv("Xem mỗi giờ", `${num(v.vph)}${v.recent_vph != null ? " <small class='note'>(giữa 2 lần quét)</small>" : " <small class='note'>(trung bình)</small>"}`)
        + kv("Tuổi video", v.created_ts ? `${fmtDate(v.created_ts)} · ${days(v.age_days)}` : "chưa rõ")
        + kv("Thích / Bình luận / Chia sẻ", `${num(v.likes)} / ${num(v.comments)} / ${num(v.shares)}`)
        + (v.engagement != null ? kv("Tỉ lệ tương tác / chia sẻ", `${v.engagement}% / ${v.share_rate}%`) : "")}
    <h3>POD</h3>
    ${kv("Loại sản phẩm", esc(v.product_type || "chưa rõ") + (v.personalized ? " · cá nhân hoá" : ""))}
    ${kv("Niche", v.niches && v.niches.length ? v.niches.map(esc).join(", ") : "chưa rõ")}
    <h3>Vì sao có nhãn này</h3>
    ${v.checks.map(c => `<div class="check">${c.ok === true ? "✅" : c.ok === false ? "❌" : "➖"} ${esc(c.text)}</div>`).join("")}
    ${v.platform !== "tiktok_ads" && v.snapshots.length ? `<h3>Các lần quét (${v.snapshots.length})</h3>
      <table><tr><th>Lúc</th><th>Lượt xem</th><th>Thích</th><th>Chia sẻ</th></tr>${v.snapshots.slice().reverse().map(s =>
        `<tr><td>${new Date(s.ts * 1000).toLocaleString()}</td><td>${num(s.views)}</td><td>${num(s.likes)}</td><td>${num(s.shares)}</td></tr>`).join("")}</table>` : ""}`;
  $("#drawer").classList.remove("hidden");
}

// ---------------- Chế độ an toàn ----------------

const SITE = {facebook: "facebook", tiktok: "tiktok", pinterest: "pinterest"};
const PNAME = {facebook: "Facebook", tiktok: "TikTok", pinterest: "Pinterest"};

function renderAlert(blocked) {
  const keys = Object.keys(blocked || {});
  $("#cnt-safety").textContent = keys.length ? "!" : "";
  $("#pills").innerHTML = ["facebook", "tiktok", ...(blocked.pinterest ? ["pinterest"] : [])].map(p => `<span class="pill ${blocked[p] ? "bad" : ""}" ${act("goSafety")}
    title="${blocked[p] ? esc(blocked[p].reason) : "Đang quét bình thường"}"><i></i>${PNAME[p]}</span>`).join("");
  $("#alert").innerHTML = keys.map(p => `<div class="alert"><div>⚠️</div><div>
      <b>${esc(blocked[p].reason)}</b> <span class="note">(${ago(blocked[p].ts)})</span><br>
      ${NOUN} đã <b>tạm dừng mọi lượt quét ${PNAME[p] || p}</b> để bảo vệ tài khoản.
      Bấm "Mở trang để xác minh", tự làm theo hướng dẫn của ${PNAME[p] || p},
      đóng tab, nên đợi vài tiếng rồi bấm "Đã xử lý, quét tiếp".</div>
      <div class="acts"><button class="small" ${act("openLogin", SITE[p])}>Mở trang để xác minh</button>
      <button class="small primary" ${act("resumePlatform", p)}>Đã xử lý, quét tiếp</button></div></div>`).join("");
}

async function renderSafety() {
  const [{platforms, tips}, bundles] = await Promise.all([api("/api/safety"), api("/api/diag")]);
  return `<p class="note">${NOUN} không che giấu việc tự động hoá. Nó giảm nguy cơ bị checkpoint bằng cách quét chậm như người thật,
    giới hạn số lần quét mỗi ngày, và <b>dừng ngay</b> khi Facebook/TikTok hiện checkpoint, captcha hoặc bắt đăng nhập lại.</p>
    <div class="cards" style="grid-template-columns:repeat(auto-fill,minmax(320px,1fr))">${platforms.map(p => `<div class="card">
      <div style="display:flex;align-items:center;gap:8px"><b style="font-size:16px">${esc(p.name)}</b>
        ${p.blocked ? `<span class="chip r">Tạm dừng</span>` : `<span class="chip g">Đang chạy bình thường</span>`}</div>
      ${p.blocked ? `<p class="red" style="font-weight:500">${esc(p.blocked.reason)} · ${ago(p.blocked.ts)}</p>
        <div class="toolbar"><button class="small" ${act("openLogin", SITE[p.key])}>Mở trang để xác minh</button>
        <button class="small primary" ${act("resumePlatform", p.key)}>Đã xử lý, quét tiếp</button></div>` : ""}
      <div class="kv"><span>Đã quét hôm nay</span><b>${p.used_today} / ${p.max_per_day}</b></div>
      <div class="kv"><span>Lần quét gần nhất</span><b>${ago(p.last_ts)}</b></div>
      <form class="toolbar limitsForm" data-platform="${p.key}" style="margin:10px 0 0">
        <label class="note">Nghỉ tối thiểu <input name="min_gap_s" type="number" min="30" max="3600" value="${p.min_gap_s}" style="width:80px"> giây</label>
        <label class="note">Tối đa <input name="max_per_day" type="number" min="1" max="500" value="${p.max_per_day}" style="width:70px"> lần/ngày</label>
        <button class="small">Lưu</button>
        <button type="button" class="small" ${act("openLogin", SITE[p.key])}>Đăng nhập ${esc(p.name)}</button></form>
    </div>`).join("")}</div>
    <div class="card"><b>Lời khuyên để tài khoản an toàn</b><ul class="tips">${tips.map(t => `<li>${esc(t)}</li>`).join("")}</ul></div>
    ${diagSection(bundles)}`;
}

// ---------------- Thông báo + gói chẩn đoán ----------------

const EVENT_NAMES = {sap_win: "Video Sắp WIN mới", win: "Video Win mới", viral: "Video TikTok/Reels Đang nổ hoặc Viral mới",
  follow: "Page/shop đang theo dõi lên QC mới"};

async function renderNotify() {
  const n = await api("/api/notify");
  return `<div class="cards" style="grid-template-columns:repeat(auto-fill,minmax(360px,1fr))">
    <div class="card"><b style="font-size:16px">Telegram (điện thoại)</b>
      <ol class="tips">
        <li>Mở Telegram, tìm <b>@BotFather</b>, gửi <code>/newbot</code>, đặt tên → nhận <b>token</b>.</li>
        <li>Dán token vào ô dưới rồi bấm <b>Lưu</b>.</li>
        <li>Mở bot vừa tạo, bấm <b>Start</b> (gửi /start).</li>
        <li>Bấm <b>Tự lấy chat ID</b>, rồi <b>Gửi thử</b>.</li></ol>
      <form class="toolbar" id="notifyForm" style="margin-top:10px">
        <input name="telegram_token" type="password" placeholder="${n.has_token ? "Đã lưu token " + esc(n.token_hint) + " (nhập để đổi)" : "Token bot, vd 123456:ABC..."}" style="flex:1;min-width:220px" autocomplete="off">
        <input name="telegram_chat_id" placeholder="Chat ID" value="${esc(n.telegram_chat_id)}" style="width:140px">
        <button class="small primary">Lưu</button></form>
      <div class="toolbar"><button class="small" ${act("findChat")}>Tự lấy chat ID</button>
        <button class="small" ${act("testNotify")}>Gửi thử</button>
        ${n.has_token ? `<button class="small" ${act("clearToken")}>Xoá token</button>` : ""}</div>
      <p class="note" style="margin:0">Token chỉ lưu ${IS_EXT ? "trong Chrome " : ""}trên máy bạn.</p></div>
    <div class="card"><b style="font-size:16px">Báo khi nào</b>
      <form id="eventsForm" style="margin-top:8px">${Object.entries(EVENT_NAMES).map(([k, name]) =>
        `<label class="check" style="display:block"><input type="checkbox" name="${k}" ${n.events[k] ? "checked" : ""}> ${name}</label>`).join("")}
        <label class="check" style="display:block;margin-top:10px"><input type="checkbox" name="desktop" ${n.desktop ? "checked" : ""}> Hiện thông báo góc màn hình ${IS_EXT ? "(của Chrome)" : "Windows"}</label>
        <button class="small" style="margin-top:10px">Lưu</button></form>
      <p class="note">Mỗi video chỉ báo 1 lần. Video đã có từ trước khi bật thông báo sẽ không bị báo lại.</p></div></div>`;
}

async function findChat() {
  try { const n = await post("/api/notify/find-chat"); alert("Đã lấy chat ID: " + n.telegram_chat_id); render(); }
  catch (e) { alert(e.message); }
}
async function testNotify() {
  try { const r = await post("/api/notify/test"); alert("Đã gửi tới: " + r.sent.join(", ") + (r.errors.length ? "\nLỗi: " + r.errors.join("; ") : "")); }
  catch (e) { alert(e.message); }
}
async function clearToken() { await post("/api/notify", {telegram_token: ""}); render(); }

function diagSection(bundles) {
  const size = b => b < 1024 * 1024 ? (b / 1024).toFixed(0) + " KB" : (b / 1024 / 1024).toFixed(1) + " MB";
  return `<div class="card" style="margin-top:12px"><b>Gói chẩn đoán</b>
    <p class="note">${NOUN} tự lưu khi 1 lượt quét ra 0 kết quả, lỗi, hoặc gặp checkpoint (giữ 15 gói gần nhất).
    Tải về và gửi cho người hỗ trợ để sửa nhanh. Email đã được che, nhưng trang có thể chứa <b>tên tài khoản</b> của bạn — xem trước khi gửi.</p>
    ${bundles.length ? `<table><tr><th>Lúc</th><th>Lượt quét</th><th>Lỗi</th><th>Phản hồi</th><th></th></tr>${bundles.map(b =>
      `<tr><td>${ago(b.ts)}</td><td>${esc(b.label || "")}</td><td>${esc((b.error || "").slice(0, 80))}</td><td>${b.responses ?? "?"} · ${size(b.size)}</td>
       <td><button class="small" ${act("downloadDiag", b.name)}>Tải .zip</button></td></tr>`).join("")}</table>`
      : `<p class="note">Chưa có gói nào — mọi lượt quét đều ra kết quả.</p>`}</div>`;
}

async function resumePlatform(p) { await post(`/api/safety/resume/${p}`); pollJobs(); render(); }
async function openLogin(site) {
  try { await post(`/api/login/${site}`); if (!IS_EXT) alert("Đã mở cửa sổ trình duyệt của tool. Làm xong thì đóng cửa sổ đó."); }
  catch (e) { alert(e.message); }
}

async function removeViralKw(platform, keyword, country) {
  await del(`/api/viral/keywords/${platform}/${enc(keyword || " ")}${country ? "?country=" + enc(country) : ""}`); render();
}

async function renderOverview() {
  const [s, auto, niches, vir, info, hot] = await Promise.all([refreshCounts(), api("/api/autoscan"), api("/api/niches"),
    api("/api/viral").catch(() => ({counts: {}})), api("/api/info"), api("/api/videos?tab=hot&limit=10").catch(() => ({items: []}))]);
  const welcome = info.has_data ? (info.demo ? `<div class="card" style="margin-bottom:14px">Đang xem <b>dữ liệu mẫu</b>.
      Lượt quét thật đầu tiên sẽ tự xoá dữ liệu mẫu. <a ${act("setView", "scan")}><b>Quét từ khoá →</b></a></div>` : "")
    : `<div class="card" style="margin-bottom:14px"><b style="font-size:16px">Chào mừng tới SNAKEMEDIA POD 🐍</b>
      ${IS_EXT ? `<p class="note">Bắt đầu: đăng nhập Facebook trên Chrome này, rồi vào <a ${act("setView", "scan")}><b>Quét từ khoá</b></a>.
      Hoặc tự mở Thư viện quảng cáo Facebook và lướt — tiện ích tự lưu QC bạn xem.</p>
      <button class="small" ${act("loadDemo")}>Xem thử với dữ liệu mẫu</button>`
      : `<p class="note">Bắt đầu: đăng nhập Facebook 1 lần (menu Start → "Đăng nhập Facebook"), rồi vào
      <a ${act("setView", "scan")}><b>Quét từ khoá</b></a>. Muốn xem thử trước: menu Start → "SNAKEMEDIA POD (dữ liệu demo)".</p>`}</div>`;
  const cards = s.labels.filter(l => l.key !== "theo_doi").map(l => `<a class="card" ${act("setView", l.key)}><div class="big">${l.count}</div>${l.name}</a>`).join("");
  const topN = niches.filter(n => n.sap_win + n.win + n.scale).slice(0, 6);
  const tb = s.tabs || {};
  const tabCard = (key, icon, name, n, sub) => `<a class="card" ${act("setView", key)}><div class="big">${n || 0}</div>${icon} ${name}<div class="note">${sub}</div></a>`;
  const hotGrid = hot.items.length ? `<div class="toolbar" style="margin:0 0 8px"><b style="font-size:15px">Video nổi bật</b>
      <span class="note">— Sắp WIN / Win / Scale / Tiềm năng, video mới nhất trước</span>
      <a class="small" style="margin-left:auto" ${act("setView", "potential")}>Xem thêm →</a></div>
    <div class="grid">${hot.items.map((v, i) => fbCard(v, i)).join("")}</div>` : "";
  return welcome + hotGrid + `<div class="cards">${cards}</div>
    <div class="cards">
      ${tabCard("potential", "🌱", "Video Tiềm Năng", tb.potential, "vừa nhú, chưa chín")}
      ${tabCard("cow", "🐄", "SP bò sữa", tb.cow, "chạy đều nhiều tuần")}
      ${tabCard("dig", "⤓", "Chờ đào sâu", tb.dig, "Sắp WIN / Tiềm năng chưa đào")}
      ${tabCard("stores", "🏪", "Store chờ soi", tb.stores, "shop đang chạy video hot")}
    </div>
    <div class="card" style="margin-bottom:14px"><b>Nên xem tab nào?</b> <span class="note">— tuỳ kênh bạn đang giỏi</span>
      <div class="note" style="margin-top:6px">• <b>Chạy Facebook</b>: <a ${act("setView", "win")}>Video Win</a> + <a ${act("setView", "scale")}>Video scale</a> — hàng đã được nhiều shop chứng minh ra đơn và đang nhân bản.<br>
      • <b>Chạy TikTok</b>: thêm <a ${act("setView", "potential")}>Video Tiềm Năng</a> — bắt con đang nhú trước khi trend tràn khắp nơi.<br>
      • <b>Google Shopping / Search, SEO, sàn, free traffic</b>: <a ${act("setView", "cow")}>SP bò sữa</a> — hàng sống dai nhiều tuần.</div></div>
    <div class="cards">
      <a class="card" ${act("setView", "keywords")}><div class="note">Tự quét mỗi đêm</div>
        <b>${auto.enabled ? `Bật · ${auto.hour}h` : "Đang tắt"}</b><div class="note">${auto.keywords} từ khoá · ${auto.follows} page/shop<br>Lần gần nhất: ${auto.last_date || "chưa"}</div></a>
      <a class="card" ${act("setView", "viral")}><div class="note">Video viral TikTok / Reels</div>
        <div><b class="red">${vir.counts.dang_no || 0}</b> đang nổ · <b>${vir.counts.viral || 0}</b> viral</div>
        <div class="note">${vir.counts.dang_len || 0} đang lên · ${vir.counts.top_ads || 0} Top Ads</div></a>
      <a class="card" style="grid-column:span 2" ${act("setView", "niches")}><div class="note">Niche POD đang nóng</div>
        ${topN.length ? topN.map(n => `<div>🎯 ${esc(n.niche)} <span class="note">· ${n.sap_win} sắp win · ${n.win} win</span></div>`).join("") : '<div class="note">Chưa đủ dữ liệu</div>'}</a>
    </div>
    <div class="card"><h3 style="margin-top:0">Luật chấm (không có điểm AI)</h3>
    <div class="note">• <b>Sắp WIN</b>: video ≤ 14 ngày tuổi, trang bán không cũ hơn video quá 14 ngày, ≥ 2 shop đang chạy.<br>
    • <b>Video Win</b>: video ≤ 30 ngày, ≥ 2 shop giữ quảng cáo sống 7–14 ngày (có người đổ tiền thật và giữ lại).<br>
    • <b>Video scale</b>: 1 shop bơm ≥ 5 quảng cáo mới trong 7 ngày.<br>
    • <b>Trang bán cũ</b>: trang sản phẩm tạo trước video quá 14 ngày → người ta ăn no rồi.<br>
    • <b>Video già</b>: quảng cáo sớm nhất (tính cả QC đã tắt, mọi shop) quá 30 ngày.<br>
    • <b>POD</b>: nhận ra loại sản phẩm (áo, cốc, ornament…), niche (chó, mẹ, y tá…), hàng cá nhân hoá và app POD trên trang bán.<br>
    • Dấu <b>*</b> sau "URL x ngày" = tuổi trang là ước tính (không có dữ liệu ngày tạo trực tiếp).<br>
    Các ngưỡng sửa trong <code>${CONFIG_FILE}</code>, từ khoá POD/niche sửa trong <code>${IS_EXT ? "lib/pod.js" : "snakepod/pod.py"}</code>.</div></div>
    <h3>Lượt quét gần đây</h3>${scansTable(s.scans)}`;
}

function scansTable(scans) {
  if (!scans.length) return `<div class="note">Chưa quét lần nào.</div>`;
  return `<div class="list"><table><tr><th>Việc</th><th>Trạng thái</th><th>Số QC</th><th>Bắt đầu</th></tr>${scans.map(s =>
    `<tr><td>${esc(s.target)}</td><td>${esc(s.status)}${s.error ? ` <span class="red" title="${esc(s.error)}">(lỗi)</span>` : ""}</td>
     <td>${s.n_ads}</td><td>${ago(s.started_ts)}</td></tr>`).join("")}</table></div>`;
}

async function renderScan() {
  const [scans, passive, jobs] = await Promise.all([api("/api/scans"),
    IS_EXT ? api("/api/passive") : Promise.resolve(null), api("/api/jobs")]);
  const left = `<form class="scan" id="scanForm">
      <input name="keyword" placeholder="Từ khoá, vd: personalized dog shirt, nurse mug…" required>
      <input name="country" value="US" size="3" title="Mã quốc gia">
      <input name="max_ads" type="number" value="300" style="width:90px" title="Số QC tối đa">
      <label class="note"><input type="checkbox" name="save" checked> Lưu để tự quét mỗi đêm</label>
      <button class="primary">Quét</button></form>
    <div class="card" style="margin:0 0 12px" id="kwBox">${await kwSuggestBox()}</div>
    <form class="card" id="batchForm" style="margin:0 0 12px">
      <b>Quét hàng loạt</b> <span class="note">— mỗi dòng 1 từ khoá, ${NOUN.toLowerCase()} xếp hàng quét lần lượt (có nghỉ an toàn giữa các lượt)</span>
      <textarea name="keywords" rows="4" placeholder="lawn mower&#10;garden ideas&#10;dog mom shirt" style="width:100%;margin:8px 0"></textarea>
      <div class="toolbar" style="margin:0"><input name="country" value="US" size="3" title="Quốc gia">
        <label class="note"><input type="checkbox" name="save" checked> Lưu để tự quét mỗi đêm</label>
        <button class="primary small">Xếp hàng quét</button></div></form>
    <div class="note">Gợi ý từ khoá POD (bấm để điền):</div>
    <div class="chips">${POD_KEYWORDS.map(k => `<span class="chip" ${act("fillKw", k)}>${esc(k)}</span>`).join("")}</div>
    <p class="note">${IS_EXT ? `Tiện ích mở 1 cửa sổ Chrome, vào Thư viện quảng cáo Facebook, cuộn và đọc QC video (cả QC đã tắt).
    <b>Để cửa sổ đó hiện trên màn hình đến khi quét xong</b> (Chrome ngừng tải trang bị thu nhỏ).`
      : "Tool mở cửa sổ Chromium, vào Thư viện quảng cáo Facebook, cuộn và đọc QC video (cả QC đã tắt)."}
    Sau đó tải thumbnail để gom QC trùng video, đọc tuổi trang bán, nhận diện POD, rồi chấm lại. Có thể xếp hàng nhiều từ khoá.</p>
    ${passive ? `<div class="card" style="margin:12px 0"><label class="check"><input type="checkbox" data-change="passive" ${passive.enabled ? "checked" : ""}>
      <b>Tự lưu khi lướt</b></label>
      <p class="note" style="margin:4px 0 0">Khi bạn tự mở Thư viện quảng cáo Facebook, TikTok hoặc TikTok Creative Center trên Chrome,
      tiện ích lưu luôn các QC / video bạn lướt qua (không tính vào giới hạn quét, không tự cuộn).</p></div>` : ""}`;
  return `<div class="split"><div>${left}</div><aside><div class="card" id="progress">${progressPanel(jobs.progress)}</div></aside></div>
    <h3>Lượt quét gần đây</h3>${scansTable(scans)}`;
}

// ---------------- gợi ý từ khoá: Pinterest / Google Trends / Tự đào ----------------

let kwTab = "pinterest", kwMarket = "US";
const KW_TABS = {pinterest: "Pinterest", google: "Google Trends", auto: "Tự đào"};
const KW_NOTES = {
  pinterest: "Từ khoá đang tăng trên Pinterest Trends, xếp theo % tăng. Người dùng Pinterest lên kế hoạch mua trước vài tuần — hợp để đón mùa sale.",
  google: "Tìm kiếm đang thịnh hành trên Google (RSS công khai của Google Trends): nhiều tin tức / thể thao, chọn những từ liên quan sản phẩm.",
  auto: "Lấy từ tên sản phẩm / nội dung các video đang hot trong kho mà bạn chưa quét.",
};

async function kwSuggestBox() {
  const tabs = `<div class="seg kwtabs">${Object.entries(KW_TABS).map(([k, n]) => `<button class="small ${kwTab === k ? "on" : ""}" ${act("kwTab", k)}>${n}</button>`).join("")}</div>`;
  let rows = [], head = "", foot = "";
  if (kwTab === "auto") {
    const sug = await api("/api/keywords/suggest").catch(() => []);
    rows = sug.map(k => ({term: k.keyword, info: `${k.source} · ${k.videos} video`, metric: `${k.videos} video`, scanned: false}));
  } else {
    const [r, mk] = await Promise.all([api(`/api/kwtrends?source=${kwTab}&market=${kwMarket}`), getMarkets()]);
    rows = r.items.map(it => ({term: it.term, info: [it.group, it.info].filter(Boolean).join(" · "), scanned: it.scanned,
      metric: it.growth != null ? `<b class="chip ${it.growth > 0 ? "o" : ""}">${it.growth > 0 ? "+" : ""}${it.growth}%</b>` : it.score ? num(it.score) : ""}));
    head = `<div class="toolbar" style="margin:6px 0">
      <select data-change="kwMarket">${Object.entries(mk.markets).map(([c, n]) => `<option value="${c}" ${c === kwMarket ? "selected" : ""}>${c} · ${esc(n)}</option>`).join("")}</select>
      <button class="small" ${act("refreshKwTrends")}>↻ Lấy mới</button>
      <span class="note">${r.ts ? `${r.items.length} từ · ${r.unscanned} chưa quét · lấy ${ago(r.ts)}` : "Chưa lấy lần nào — bấm Lấy mới"}</span></div>`;
    if (kwTab === "pinterest") foot = `<p class="note">Pinterest Trends: ${NOUN.toLowerCase()} mở trang trends.pinterest.com bằng ${IS_EXT ? "cửa sổ Chrome" : "trình duyệt quét"} và đọc dữ liệu của trang
      (thử nghiệm — Pinterest có thể bắt đăng nhập: mục Chế độ an toàn → Đăng nhập Pinterest). Ra 0 từ thì gửi gói chẩn đoán.</p>`;
  }
  const list = rows.length ? `<div class="kwlist"><table>
      <tr><th><input type="checkbox" ${act("toggleAllKw")} title="Chọn tất cả từ chưa quét"></th><th>Từ khoá</th><th class="num">${kwTab === "pinterest" ? "Tăng" : kwTab === "google" ? "Lượt tìm" : ""}</th><th></th></tr>
      ${rows.map(r => `<tr class="${r.scanned ? "dim" : ""}"><td><input type="checkbox" class="kwpick" value="${esc(r.term)}"></td>
        <td>${esc(r.term)}${r.info ? `<br><small class="note">${esc(r.info)}</small>` : ""}</td><td class="num">${r.metric}</td>
        <td class="num"><small class="note">${r.scanned ? "đã quét" : "chưa quét"}</small></td></tr>`).join("")}</table></div>
      <div class="toolbar" style="margin:8px 0 0"><button class="primary small" ${act("scanSelected")}>Quét các từ đã chọn</button>
        <label class="note"><input type="checkbox" id="kwSave" checked> Lưu để tự quét mỗi đêm</label></div>`
    : `<div class="note" style="padding:10px 0">${kwTab === "auto" ? "Chưa có gợi ý — cần vài video hot trong kho trước." : "Chưa có dữ liệu."}</div>`;
  return `<b>Gợi ý từ khoá</b> ${tabs}<p class="note" style="margin:6px 0 0">${KW_NOTES[kwTab]}</p>${head}${list}${foot}`;
}

async function refreshKwTrends() {
  const r = await post("/api/kwtrends/refresh", {source: kwTab, countries: [kwMarket]});
  pollJobs();
  if (!r.queued) alert("Đang lấy rồi, chờ chút nhé.");
}

function toggleAllKw() {
  const boxes = [...document.querySelectorAll(".kwpick")];
  const on = !boxes.some(b => b.checked);
  boxes.forEach(b => { b.checked = on && !b.closest("tr").classList.contains("dim"); });
}

async function scanSelected() {
  const keywords = [...document.querySelectorAll(".kwpick:checked")].map(b => b.value);
  if (!keywords.length) return alert("Chọn ít nhất 1 từ khoá");
  const r = await post("/api/scan", {keywords, country: kwTab === "auto" ? "US" : kwMarket, max_ads: 300, save: !!($("#kwSave") || {}).checked});
  pollJobs(); alert(`Đã xếp ${r.queued} từ khoá vào hàng quét.`); render();
}

// ---------------- bảng tiến độ quét ----------------

const fmtDur = s => s == null ? "?" : s < 60 ? `${s} giây` : s < 3600 ? `${Math.round(s / 60)} phút` : `${Math.floor(s / 3600)} giờ ${Math.round(s % 3600 / 60)} phút`;
const ST = {xong: ["", "g"], "da dung": ["đã dừng", ""], "bo qua": ["bỏ qua", "o"], checkpoint: ["checkpoint", "r"], loi: ["lỗi", "r"]};

function progressPanel(p) {
  if (!p || !p.total) return `<b>Tiến độ quét</b><p class="note">Chưa có lượt quét nào đang chạy. Chọn từ khoá bên trái rồi bấm Quét —
    ${NOUN.toLowerCase()} xếp hàng và quét lần lượt, có nghỉ an toàn giữa các lượt.</p>`;
  const c = p.current, n = p.n_done + (c ? 1 : 0);
  const line = (dot, title, right) => `<div class="pline"><i class="dot ${dot}"></i><span>${esc(title)}</span><small class="note">${right}</small></div>`;
  return `<div class="toolbar" style="margin:0"><b>${c ? `Đang quét · ${n} / ${p.total}` : `Xong ${p.n_done} / ${p.total}`}</b>
      ${c ? `<button class="small danger" style="margin-left:auto" ${act("stopJobs")}>Dừng</button>` : ""}</div>
    ${c ? `<div class="pcur"><span class="spin"></span><div><b>${esc(c.title)}</b><div class="note">${c.count} đã đọc · chạy ${fmtDur(c.secs)}</div></div></div>` : ""}
    <div class="plist">${p.done.slice().reverse().map(d => line(ST[d.status] ? ST[d.status][1] : "", d.title,
        (d.status === "xong" ? `${d.n}` : ST[d.status] ? ST[d.status][0] : d.status) + ` · ${fmtDur(d.secs)}`)).join("")}
      ${p.pending.slice(0, 12).map(t => line("w", t, "chờ")).join("")}${p.pending.length > 12 ? `<div class="note">… +${p.pending.length - 12} việc chờ</div>` : ""}</div>
    <div class="pfoot"><div><b>${p.rate != null ? `~${p.rate}` : "—"}</b><small>QC / phút</small></div>
      <div><b>${p.items}</b><small>đã đọc phiên này</small></div>
      <div><b>${c || p.pending.length ? fmtDur(p.eta_s) : "xong"}</b><small>còn lại (ước tính)</small></div></div>
    <p class="note" style="margin:8px 0 0">Có thể đóng ${IS_EXT ? "trang này" : "cửa sổ trình duyệt"} — ${NOUN.toLowerCase()} vẫn quét tiếp${IS_EXT ? " (giữ Chrome mở)" : ""}. Thời gian còn lại tính theo các việc đã xong, gồm cả thời gian nghỉ an toàn.</p>`;
}

// ---------------- Kết nối Shopify + Clone ----------------

async function renderShopify() {
  const s = await api("/api/shopify");
  const scopes = s.scopes;
  return `<div class="card" style="max-width:820px">
    ${s.connected ? `<div class="toolbar" style="margin:0 0 8px"><span class="chip g">Đã kết nối</span><b>${esc(s.name)}</b>
      <span class="note">${esc(s.shop)}${s.currency ? " · " + esc(s.currency) : ""} · đã clone ${s.clones} sản phẩm</span>
      <button class="small" style="margin-left:auto" ${act("disconnectShopify")}>Ngắt kết nối</button></div>` : ""}
    <p class="note">Kết nối 1 lần để nút <b>⧉ Clone</b> đưa sản phẩm của trang bán (tên, mô tả, ảnh, biến thể, giá, giá gạch) vào store của bạn
    dưới dạng <b>bản nháp (Draft)</b> — không tự đăng bán. Bạn tự tạo 1 app riêng cho store mình trong Shopify, khoảng 5 phút.
    App chỉ dùng được trên store của bạn và bạn xoá được bất cứ lúc nào.</p>
    <ol class="steps">
      <li>Mở <a target="_blank" rel="noopener" href="https://dev.shopify.com/dashboard">dev.shopify.com/dashboard</a> bằng tài khoản Shopify đang sở hữu store
        → <b>Apps</b> → <b>Create app</b> → <b>Create app manually</b>.</li>
      <li>Điền <b>App name</b> (vd "SNAKEMEDIA Clone"), <b>App URL</b> điền <code>https://example.com</code>, ô <b>Scopes</b> dán:
        <div class="toolbar"><code class="copy">${esc(scopes)}</code><button type="button" class="small" ${act("copyText", scopes)}>Sao chép</button></div>
        Bấm <b>Create app</b>, rồi bấm <b>Release</b> ở hộp hiện ra.</li>
      <li>Ở trang <b>Overview</b> của app → <b>Install app</b> → chọn store của bạn → <b>Install</b>.</li>
      <li>Vẫn ở <b>Overview</b>, mục <b>Credentials</b> → sao chép <b>Client ID</b> và <b>Client secret</b>.</li>
      <li>Dán vào đây cùng tên store dạng <code>ten-store.myshopify.com</code> (Shopify admin → Settings → Domains).</li>
    </ol>
    <form id="shopifyForm">
      <label class="field">Tên store<input name="shop" placeholder="ten-store.myshopify.com" value="${esc(s.shop || "")}" required></label>
      <label class="field">Client ID<input name="client_id" value="${esc(s.client_id || "")}" autocomplete="off"></label>
      <label class="field">Client secret<input name="client_secret" type="password" autocomplete="off"
        placeholder="${s.secret_masked ? "Đã lưu (" + esc(s.secret_masked) + ") — để trống nếu không đổi" : ""}"></label>
      <p class="note">Client secret chỉ lưu trên ${IS_EXT ? "máy bạn (trong hồ sơ Chrome)" : "máy bạn (file dữ liệu của tool)"}, không gửi đi đâu ngoài Shopify.
      Store cũ dùng "custom app" trong Shopify admin? Dán <b>Admin API access token</b> (<code>shpat_…</code>) vào ô Client secret, để trống Client ID.</p>
      <button class="primary">${s.connected ? "Lưu & kết nối lại" : "Kết nối"}</button>
    </form></div>
    <div class="card" style="max-width:820px;margin-top:12px"><b>Lưu ý khi clone</b>
      <ul class="tips"><li>Ảnh và mô tả của shop khác có bản quyền: sửa lại mô tả, chụp / làm ảnh riêng trước khi bán.</li>
      <li>Sản phẩm vào store ở trạng thái <b>Draft</b> với tag <code>snakemedia-clone</code>; tự đặt giá, tồn kho, vận chuyển rồi mới bật bán.</li>
      <li>Trang Shopify clone được đủ biến thể / ảnh. Nền tảng khác chỉ lấy được tên, 1–vài ảnh, giá và mô tả ngắn.</li></ul></div>`;
}

async function cloneVideo(cid, url) {
  const st = await api("/api/shopify");
  if (!st.connected) { if (confirm("Chưa kết nối Shopify. Mở trang Kết nối Shopify?")) setView("shopify"); return; }
  if (!confirm(`Clone sản phẩm${url ? " từ " + url.replace(/^https?:\/\//, "").slice(0, 60) : ""} vào store ${st.name} (bản nháp)?`)) return;
  try {
    const r = await post("/api/shopify/clone", {cid, url: url || null});
    if (confirm(`Đã tạo bản nháp "${r.title}" (${r.variants} biến thể, ${r.images} ảnh). Mở trong Shopify?`)) window.open(r.admin_url, "_blank", "noopener");
    render(); if (openCid) openDrawer(openCid);
  } catch (e) { alert("Không clone được: " + e.message); }
}

async function disconnectShopify() {
  if (!confirm("Ngắt kết nối Shopify? (Sản phẩm đã clone vẫn nằm trong store)")) return;
  await del("/api/shopify"); render();
}

async function renderNiches() {
  const rows = await api("/api/niches");
  if (!rows.length) return `<div class="empty">Chưa có video POD nào. Hãy quét vài từ khoá POD trước.</div>`;
  return `<p class="note">Niche được xếp theo số video Sắp WIN + Win. Bấm tên niche để xem video.</p>
    <div class="list"><table><tr><th>Niche</th><th class="num">Sắp WIN</th><th class="num">Win</th><th class="num">Scale</th>
    <th class="num">Tổng video</th><th class="num">QC/ngày</th><th>Loại SP chính</th><th>Video nổi bật</th></tr>
    ${rows.map(r => `<tr><td><a ${act("niche", r.niche, true)}><b>${esc(r.niche)}</b></a></td>
      <td class="num">${r.sap_win}</td><td class="num">${r.win}</td><td class="num">${r.scale}</td><td class="num">${r.total}</td>
      <td class="num">${r.ads_per_day}</td><td>${r.types.map(esc).join(", ")}</td>
      <td>${r.top ? `<a ${act("openDrawer", r.top.cid)}>${esc(r.top.title.slice(0, 50))}</a>` : ""}</td></tr>`).join("")}</table></div>`;
}

async function renderFollows() {
  const rows = await api("/api/follows");
  const form = `<form class="toolbar" id="followForm">
      <select name="kind"><option value="shop">Shop (domain)</option><option value="page">Page Facebook (ID)</option></select>
      <input name="key" placeholder="vd: bloomyard.com hoặc 1234567890" required>
      <button class="primary small">+ Theo dõi</button>
      <span class="note">Hoặc bấm nút + cạnh tên shop/page trong bảng chi tiết video / Kho shop.</span></form>`;
  if (!rows.length) return form + `<div class="empty">Chưa theo dõi page/shop nào.</div>`;
  return form + `<div class="list"><table><tr><th>Page / Shop</th><th class="num">QC đang chạy</th><th class="num">Mới 24h</th>
    <th class="num">Mới 7 ngày</th><th class="num">Vừa tắt (2 ngày)</th><th>Quét lần cuối</th><th></th></tr>
    ${rows.map(f => `<tr><td>${f.kind === "page" ? "📄" : "🏪"} <a ${act("showScope", f.kind, f.key, f.name || f.key)}><b>${esc(f.name || f.key)}</b></a>
        ${f.kind === "page" ? `<small class="note">${esc(f.key)}</small>` : ""}</td>
      <td class="num">${f.active}/${f.ads}</td><td class="num ${f.new_24h ? "green" : ""}">${f.new_24h}</td><td class="num">${f.new_7d}</td>
      <td class="num ${f.off_2d ? "red" : ""}">${f.off_2d}</td><td>${ago(f.last_scan_ts)}</td>
      <td><button class="small" ${act("scanFollow", f.kind, f.key)}>Quét</button>
          <button class="small" ${act("unfollow", f.kind, f.key)}>Bỏ</button></td></tr>`).join("")}</table></div>`;
}

async function renderKeywords() {
  const [auto, kws] = await Promise.all([api("/api/autoscan"), api("/api/keywords")]);
  const hours = Array.from({length: 24}, (_, h) => `<option value="${h}" ${h === +auto.hour ? "selected" : ""}>${h}h</option>`).join("");
  return `<div class="card" style="margin-bottom:14px">
      <form class="toolbar" id="autoForm" style="margin:0">
        <label><input type="checkbox" name="enabled" ${auto.enabled ? "checked" : ""}> Tự quét mỗi đêm lúc</label>
        <select name="hour">${hours}</select>
        <label class="note">+ soi <input name="stores" type="number" min="0" max="200" value="${auto.stores}" style="width:60px"> store/đêm</label>
        <button class="small">Lưu</button>
        <button type="button" class="primary small" ${act("runAll")}>Quét tất cả ngay</button>
      </form>
      <p class="note" style="margin-bottom:0">Mỗi đêm ${NOUN.toLowerCase()} quét lại ${auto.keywords} từ khoá dưới đây và ${auto.follows} page/shop ở
      <a ${act("setView", "follows")}>Theo dõi đặc biệt</a>, rồi soi thêm ${auto.stores} shop ở <a ${act("setView", "stores")}>Quét store win</a>.
      Lần gần nhất: ${auto.last_date || "chưa"}.
      ${IS_EXT ? "<b>Chrome phải đang mở</b> (máy không tắt/ngủ) vào giờ đó. Lỡ giờ thì lần mở Chrome sau không tự bù."
        : '<b>Tool phải đang mở</b> (máy không tắt/ngủ) vào giờ đó. Bản cài đặt có tuỳ chọn "Tự mở cùng Windows".'}</p></div>
    <form class="toolbar" id="kwForm"><input name="keyword" placeholder="Thêm từ khoá…" required style="flex:1;min-width:200px">
      <input name="country" value="US" size="3"><button class="small">+ Thêm</button></form>
    ${kws.length ? `<div class="list"><table><tr><th>Từ khoá</th><th>Quốc gia</th><th>Quét lần cuối</th><th></th></tr>
      ${kws.map(k => `<tr><td><b>${esc(k.keyword)}</b></td><td>${esc(k.country)}</td><td>${ago(k.last_scan_ts)}</td>
        <td><button class="small" ${act("scanKw", k.keyword, k.country)}>Quét</button>
            <button class="small" ${act("removeKw", k.keyword)}>Xoá</button></td></tr>`).join("")}</table></div>`
      : `<div class="empty">Chưa có từ khoá nào.</div>`}`;
}

let trendMarket = "";
function spark(points) {
  const vals = (points || []).map(p => +p[1]).filter(x => !Number.isNaN(x));
  if (vals.length < 2) return "";
  const mx = Math.max(...vals), mn = Math.min(...vals), w = 90, h = 24;
  const pts = vals.map((v, i) => `${(i * w / (vals.length - 1)).toFixed(1)},${(h - 2 - (h - 4) * (mx === mn ? 0.5 : (v - mn) / (mx - mn))).toFixed(1)}`).join(" ");
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="var(--brand)" stroke-width="1.6" points="${pts}"/></svg>`;
}

async function renderTrends() {
  const [mk, r] = await Promise.all([getMarkets(), api("/api/trends" + (trendMarket ? "?market=" + enc(trendMarket) : ""))]);
  const form = `<form class="card" id="trendForm" style="margin-bottom:12px"><b>Quét hashtag xu hướng</b>
      <span class="note">— TikTok Creative Center, đúng thị trường bạn chọn (mỗi thị trường = 1 lượt quét TikTok)</span>
      <div class="chips markets" style="margin:8px 0">${Object.entries(mk.markets).map(([c, n]) =>
        `<label class="chip"><input type="checkbox" name="countries" value="${c}" ${c === "US" ? "checked" : ""}> ${c} · ${esc(n)}</label>`).join("")}</div>
      <div class="toolbar" style="margin:0"><select name="period"><option value="7">7 ngày</option><option value="30">30 ngày</option><option value="120">120 ngày</option></select>
        <label class="note"><input type="checkbox" name="save" checked> Tự quét mỗi đêm</label><button class="primary small">Quét hashtag</button></div></form>`;
  const tabs = `<div class="toolbar"><span class="seg">${["", ...r.markets].map(m =>
    `<button class="small ${trendMarket === m ? "on" : ""}" ${act("trendMarket", m)}>${m ? `${m} · ${esc(r.names[m] || m)}` : "Mọi thị trường"}</button>`).join("")}</span></div>`;
  if (!r.items.length) return form + tabs + `<div class="list"><div class="empty">Chưa có hashtag nào. Chọn thị trường ở trên rồi bấm Quét hashtag.</div></div>`;
  const move = x => x == null ? `<span class="chip g">mới</span>` : x > 0 ? `<b class="green">▲${x}</b>` : x < 0 ? `<b class="red">▼${-x}</b>` : "–";
  return form + tabs + `<p class="note">Hashtag khớp từ khoá bạn đang theo dõi được tô xanh. Bấm "Quét video" để tìm video TikTok của hashtag đó.</p>
    <div class="list"><table><tr><th class="num">Hạng</th><th></th><th>Hashtag</th><th>Thị trường</th><th class="num">Bài đăng</th><th class="num">Lượt xem</th><th>7 ngày</th><th></th></tr>
    ${r.items.map(t => `<tr ${t.match.length ? 'style="background:var(--brand-soft)"' : ""}><td class="num"><b>${t.rank ?? "?"}</b></td><td>${move(t.move)}</td>
      <td><b>#${esc(t.name)}</b>${t.match.map(m => ` <span class="chip g">${esc(m)}</span>`).join("")}</td><td>${esc(t.market)}</td>
      <td class="num">${num(t.posts)}</td><td class="num">${num(t.views)}</td><td>${spark(t.trend)}</td>
      <td><button class="small" ${act("scanTag", t.name, false)}>Quét video</button> <button class="small" ${act("scanTag", t.name, true)}>+ Theo dõi</button></td></tr>`).join("")}</table></div>`;
}

let storeFilter = "pending";
async function renderStores() {
  const r = await api(`/api/stores?status=${storeFilter}&offset=${pageOffset}&limit=50`);
  const sm = r.summary, auto = sm.auto;
  const seg = (k, name, n) => `<button class="small ${storeFilter === k ? "on" : ""}" ${act("storeFilter", k)}>${name} <b>${n}</b></button>`;
  const pct = sm.total ? Math.round(100 * sm.done / sm.total) : 0;
  const head = `<p class="note">Soi mọi shop đang chạy video ở các tab Sắp WIN / Video Win / Video scale / Tiềm năng / Bò sữa / Video test / Theo dõi
      để tìm sản phẩm khác của họ. Mỗi store = 1 lượt quét Facebook (tính vào giới hạn an toàn).</p>
    <div class="cards">
      <div class="card"><div class="big">${sm.total}</div>store win</div>
      <div class="card"><div class="big">${sm.done} <small class="note">/ ${sm.total}</small></div>đã soi trong 7 ngày
        <div class="bar" style="margin-top:8px"><i class="w" style="width:${pct}%"></i></div></div>
      <div class="card"><div class="big green">+${sm.new_videos_7d}</div>video mới từ các lượt soi đó</div>
      <div class="card"><div class="big">${auto.enabled ? String(auto.hour).padStart(2, "0") + ":00" : "tắt"}</div>ca đêm kế · ${auto.stores} store</div>
    </div>
    <div class="toolbar"><span class="seg">${seg("pending", "Chờ soi", sm.pending)}${seg("done", "Đã soi", sm.done)}${seg("all", "Tất cả", sm.total)}</span>
      <span style="margin-left:auto" class="note">Soi</span><input id="sweepN" type="number" min="1" max="100" value="10" style="width:64px">
      <button class="primary small" ${act("sweepStores")}>store đầu danh sách</button></div>`;
  if (!r.items.length) return head + `<div class="list"><div class="empty">${storeFilter === "done" ? "Chưa soi store nào trong 7 ngày."
    : "Chưa có store nào. Store xuất hiện khi có video Sắp WIN / Win / Scale / Tiềm năng / Bò sữa hoặc khi bạn theo dõi shop."}</div></div>`;
  return head + `<div class="list"><table><tr><th>Store</th><th>Video đang ở tab</th><th class="num">Quảng cáo</th><th>Soi gần nhất</th>
    <th class="num">Video mới</th><th></th></tr>
    ${r.items.map(s => `<tr><td><a ${act("showScope", "shop", s.domain, s.domain)}><b>${esc(s.domain)}</b></a>
        <br><small class="note">${esc(s.platform || "web khác")} · ${s.pages} page</small></td>
      <td>${s.tabs.map(t => `<span class="chip g">${esc(t)}</span>`).join("")}</td>
      <td class="num">${s.ads}</td>
      <td>${s.swept_ts ? `<span class="chip ${s.status === "done" ? "g" : ""}">${ago(s.swept_ts)}</span>` : `<span class="chip o">Chưa soi</span>`}</td>
      <td class="num">${s.new_videos == null ? "—" : s.new_videos ? `<b class="green">+${s.new_videos}</b>` : 0}</td>
      <td><button class="small" ${act("sweepOne", s.domain)}>Soi</button></td></tr>`).join("")}</table></div>`
    + storePager(r.total);
}

function storePager(total) {
  if (total <= 50) return "";
  const pages = Math.ceil(total / 50), cur = Math.floor(pageOffset / 50) + 1;
  return `<div class="pager"><button class="small" ${cur > 1 ? act("goPage", pageOffset - 50) : "disabled"}>← Trước</button>
    <span class="note">Trang ${cur} / ${pages} · ${total} store</span>
    <button class="small" ${cur < pages ? act("goPage", pageOffset + 50) : "disabled"}>Sau →</button></div>`;
}

async function renderHistory() {
  return `<p class="note">Mọi lượt quét / soi / đào gần đây (50 lượt).</p>${scansTable(await api("/api/scans"))}`;
}

async function renderData() {
  return `<div class="cards" style="grid-template-columns:repeat(auto-fill,minmax(340px,1fr))">
    <div class="card"><b style="font-size:16px">Xuất kho của bạn</b>
      <p class="note">Tải toàn bộ QC + tuổi trang bán đã quét ra 1 file .json để gửi cho đồng đội (không có Telegram, tài khoản hay mật khẩu).</p>
      <button class="primary small" ${act("exportData")}>⇩ Tải file dữ liệu</button></div>
    <div class="card"><b style="font-size:16px">Gộp kho của đồng đội</b>
      <p class="note">Mỗi người quét ngách của mình, gộp lại thì đếm được nhiều page / shop chạy cùng 1 video hơn hẳn quét lẻ.
      QC trùng không bị nhân đôi; mốc chạy sớm nhất và trạng thái mới nhất được giữ.</p>
      <input type="file" id="importFile" accept=".json,application/json">
      <button class="small" ${act("importData")}>⇧ Gộp vào kho</button></div></div>`;
}

async function renderShops() {
  const rows = await api("/api/shops");
  if (!rows.length) return `<div class="empty">Chưa có shop nào. Hãy quét vài từ khoá trước.</div>`;
  return `<p class="note">Mọi shop (domain trang bán) ${NOUN.toLowerCase()} từng thấy. Bấm + để theo dõi (★ = đang theo dõi), bấm tên để xem video của shop.</p>
    <div class="list"><table><tr><th></th><th>Shop</th><th>Nền tảng</th><th class="num">QC đang chạy</th><th class="num">Page</th>
    <th class="num">Video</th><th class="num">Sắp WIN/Win</th><th>QC đầu tiên</th><th>QC mới nhất</th></tr>
    ${rows.map(r => `<tr><td><button class="follow ${r.followed ? "on" : ""}" ${act("toggleFollow", "shop", r.domain, r.domain, r.followed)} title="${r.followed ? "Bỏ theo dõi" : "Theo dõi"}">${r.followed ? "★" : "+"}</button></td>
      <td><a ${act("showScope", "shop", r.domain, r.domain)}><b>${esc(r.domain)}</b></a>${r.pod ? '<span class="chip o">POD</span>' : ""}</td>
      <td>${esc(r.platform || "?")}${r.pod_markers ? ` <small class="note">${esc(r.pod_markers)}</small>` : ""}</td>
      <td class="num">${r.active || 0}/${r.ads}</td><td class="num">${r.pages}</td><td class="num">${r.videos}</td>
      <td class="num ${r.hot ? "green" : ""}">${r.hot}</td><td>${fmtDate(r.first_ts)}</td><td>${fmtDate(r.last_ts)}</td></tr>`).join("")}</table></div>`;
}

const VIEWS = {shopify: renderShopify, trends: renderTrends, stores: renderStores, history: renderHistory, data: renderData,
  potential: () => renderList(null, {tab: "potential"}), cow: () => renderList(null, {tab: "cow"}), test: () => renderList(null, {tab: "test"}),
  hidden: () => renderList(null, {tab: "hidden"}), dig: () => renderList(null, {tab: "dig"}), notify: renderNotify, safety: renderSafety, viral: renderViral, spread: () => renderList(null, {spread: "true"}), overview: renderOverview, scan: renderScan, niches: renderNiches, follows: renderFollows,
  keywords: renderKeywords, shops: renderShops};

async function render() {
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.view === view));
  $("#title").textContent = TITLES[view] || (LABEL[view] || [view])[0];
  $("#search").classList.toggle("hidden", !!VIEWS[view] && !["viral", "spread", ...TABS].includes(view));
  let html;
  try {
    html = VIEWS[view] ? await VIEWS[view]() : await renderList(view === "all" ? null : view);
  } catch (e) { html = `<div class="empty">Lỗi tải dữ liệu: ${esc(e.message)}</div>`; }
  $("#content").innerHTML = html;
  const own = e => e.target.closest("[data-act], a[href]");   // nút / link bên trong thẻ tự xử lý
  document.querySelectorAll(".row[data-cid], .gcard[data-cid], .vrow[data-cid]").forEach(r => r.onclick = e => { if (!own(e)) openDrawer(r.dataset.cid); });
  document.querySelectorAll(".row[data-vid], .gcard[data-vid]").forEach(r => r.onclick = e => { if (!own(e)) openSocial(r.dataset.vid); });
  document.querySelectorAll(".gcard[data-video]").forEach(card => {
    card.onmouseenter = () => {
      const box = card.querySelector(".gimg");
      if (box.querySelector("video")) return;
      const vd = document.createElement("video");
      Object.assign(vd, {src: card.dataset.video, muted: true, autoplay: true, loop: true, playsInline: true});
      vd.onerror = () => vd.remove();          // link video Facebook/TikTok hết hạn -> giữ ảnh
      box.appendChild(vd);
    };
    card.onmouseleave = () => card.querySelectorAll("video").forEach(x => x.remove());
  });
  bindForms();
  refreshCounts();
}

function bindForms() {
  const on = (id, fn) => { const f = $(id); if (f) f.onsubmit = async e => {
    e.preventDefault();
    try { await fn(Object.fromEntries(new FormData(f)), f); } catch (err) { alert(err.message); }
  }; };
  on("#scanForm", async (d, f) => {
    await post("/api/scan", {keyword: d.keyword, country: d.country, max_ads: +d.max_ads, save: !!d.save});
    f.keyword.value = ""; pollJobs(); render();
  });
  on("#followForm", async d => { await post("/api/follows", {kind: d.kind, key: d.key.trim(), name: d.key.trim()}); render(); });
  on("#kwForm", async d => {
    await post("/api/scan", {keyword: d.keyword, country: d.country, max_ads: 300, save: true}); pollJobs(); render();
  });
  on("#viralForm", async (d, f) => {
    const keywords = d.keywords.split(/[,\n]/).map(x => x.trim()).filter(Boolean);
    const countries = new FormData(f).getAll("countries");
    if (!countries.length) return alert("Chọn ít nhất 1 thị trường");
    const r = await post("/api/viral/scan", {platform: d.platform, keywords, countries, period: +d.period, save: !!d.save});
    f.keywords.value = ""; pollJobs(); alert(`Đã xếp ${r.queued} lượt quét.`); render();
  });
  document.querySelectorAll(".limitsForm").forEach(f => f.onsubmit = async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(f));
    try { await post("/api/safety/limits", {platform: f.dataset.platform, min_gap_s: +d.min_gap_s, max_per_day: +d.max_per_day}); render(); }
    catch (err) { alert(err.message); }
  });
  on("#notifyForm", async d => {
    await post("/api/notify", {telegram_token: d.telegram_token || null, telegram_chat_id: d.telegram_chat_id}); render();
  });
  on("#eventsForm", async d => {
    const events = Object.fromEntries(Object.keys(EVENT_NAMES).map(k => [k, !!d[k]]));
    await post("/api/notify", {events, desktop: !!d.desktop}); alert("Đã lưu"); render();
  });
  on("#trendForm", async (d, f) => {
    const countries = new FormData(f).getAll("countries");
    if (!countries.length) return alert("Chọn ít nhất 1 thị trường");
    const r = await post("/api/viral/scan", {platform: "tiktok_tags", countries, period: +d.period, save: !!d.save});
    pollJobs(); alert(`Đã xếp ${r.queued} lượt quét hashtag.`);
  });
  on("#shopifyForm", async d => {
    const r = await post("/api/shopify", d);
    alert(`Đã kết nối store ${r.name}.`); render();
  });
  on("#autoForm", async d => { await post("/api/autoscan", {enabled: !!d.enabled, hour: +d.hour, stores: +d.stores}); render(); });
  on("#batchForm", async (d, f) => {
    const keywords = d.keywords.split(/\n/).map(x => x.trim()).filter(Boolean);
    if (!keywords.length) return alert("Nhập ít nhất 1 từ khoá");
    const r = await post("/api/scan", {keywords, country: d.country, max_ads: 300, save: !!d.save});
    f.keywords.value = ""; pollJobs(); alert(`Đã xếp ${r.queued} từ khoá vào hàng quét.`); render();
  });
}

async function toggleFollow(kind, key, name, isOn) {
  if (isOn) await del(`/api/follows/${kind}/${enc(key)}`); else await post("/api/follows", {kind, key, name});
  refreshCounts();
  if (openCid) openDrawer(openCid);
  if (VIEWS[view]) render();
}
async function unfollow(kind, key) { await del(`/api/follows/${kind}/${enc(key)}`); render(); }
async function scanFollow(kind, key) { await post(`/api/follows/${kind}/${enc(key)}/scan`); pollJobs(); }
async function scanKw(keyword, country) { await post("/api/scan", {keyword, country, max_ads: 300}); pollJobs(); }
async function removeKw(keyword) { await del(`/api/keywords/${enc(keyword)}`); render(); }
async function runAll() { const r = await post("/api/autoscan/run"); pollJobs(); alert(`Đã xếp ${r.queued} việc quét.`); }

async function openDrawer(cid) {
  openCid = cid; openVid = null;
  document.querySelectorAll(".row, .vrow").forEach(r => r.classList.toggle("on", r.dataset.cid === cid));
  const v = await api(`/api/videos/${enc(cid)}`);
  const [ln, cls] = LABEL[v.label] || [v.label, ""];
  const b = v.buckets, tot = Math.max(1, b.old + b.win + b.scale);
  const pct = n => (100 * n / tot).toFixed(1) + "%";
  const img = thumb(v) ? `<img class="hero" src="${esc(thumb(v))}">` : `<div class="hero"></div>`;
  const src = v.landing_date_source ? ` <small class="note">(${DATE_SOURCE[v.landing_date_source] || v.landing_date_source})</small>` : "";
  const marks = v.marks || [], isTest = marks.includes("test"), isHidden = marks.includes("hidden");
  const digChip = v.dug_ts ? `<span class="chip g">Đã đào ${ago(v.dug_ts)}</span>`
    : (v.label === "sap_win" || v.potential) ? `<span class="chip o">${v.label === "sap_win" ? "Sắp WIN" : "Tiềm năng"} · chưa đào</span>` : "";
  const hist = v.history || [];
  const dlt = (i, k) => i + 1 < hist.length && hist[i][k] !== hist[i + 1][k] ? " " + plus(hist[i][k] - hist[i + 1][k]) : "";
  const histTable = hist.length ? `<h3>Lịch sử theo dõi <small class="note">(mỗi ngày 1 dòng, lần chấm sau cùng trong ngày)</small></h3>
    <table><tr><th>Ngày</th><th>Fanpage chạy</th><th>Shop sống</th><th>Win</th><th>Scale</th><th>URL</th></tr>
    ${hist.map((h, i) => `<tr><td>${esc(h.day.slice(8, 10) + "/" + h.day.slice(5, 7))}</td><td>${h.pages_active}${dlt(i, "pages_active")}</td>
      <td>${h.shops_active}${dlt(i, "shops_active")}</td><td>${h.shops_win}${dlt(i, "shops_win")}</td>
      <td>${h.scale}${dlt(i, "scale")}</td><td>${h.urls}${dlt(i, "urls")}</td></tr>`).join("")}</table>` : "";
  const pages = v.sell_pages || [];
  const sellList = pages.length ? `<h3>Đang bán ở ${v.urls_total} trang</h3>
    <table>${pages.map(pg => `<tr><td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
      <a target="_blank" rel="noopener" href="${esc(pg.url)}">${esc(pg.url.replace(/^https?:\/\/(www\.)?/, ""))}</a></td>
      <td><small class="note">${esc(pg.platform || "")}</small></td>
      <td class="num">${pg.price ? "$" + esc(pg.price) : ""}${pg.compare_price ? ` <s class="note">$${esc(pg.compare_price)}</s>` : ""}</td>
      <td class="num"><small class="note">${pg.created_ts ? "tạo " + dm(pg.created_ts) : ""}</small></td><td class="num">${pg.ads} QC</td>
      <td><a ${act("cloneVideo", v.cid, pg.url)} title="Clone trang này vào Shopify của bạn">⧉ Clone</a></td></tr>`).join("")}</table>` : "";
  const sourcing = (v.sourcing || []).length ? `<h3>Tìm nguồn hàng</h3><div>${v.sourcing.map(x =>
    `<a class="btn small" target="_blank" rel="noopener" href="${esc(x.url)}" style="margin:0 6px 6px 0">${esc(x.name)} ↗</a>`).join("")}</div>
    <p class="note" style="margin-top:2px">Tìm theo tên sản phẩm / ảnh để hỏi giá xưởng hoặc bên fulfill của bạn (tool không nhận hoa hồng từ bên nào).</p>` : "";
  const followBtn = (kind, key, name, on) =>
    `<button class="follow ${on ? "on" : ""}" ${act("toggleFollow", kind, key, name, on)} title="${on ? "Bỏ theo dõi" : "Theo dõi"}">${on ? "★" : "+"} ${esc(name)}</button>`;
  $("#drawer").innerHTML = `<button class="x" ${act("closeDrawer")}>✕</button>${img}
    <h2>${esc(v.title)}</h2>
    <div><span class="chip ${cls}">${ln}</span>${podChips(v)}${v.platform ? `<span class="chip">${esc(v.platform)}</span>` : ""}
${tabChips(v)}${digChip}
      <span class="note"> · ${v.pages_total} Trang · ${v.shops_total} shop · quét ${ago(v.last_seen)}</span></div>
    <div class="btns">
      <a class="btn primary" target="_blank" rel="noopener" href="${esc(v.video_url || v.ad_library_url)}">▶ Xem video</a>
      ${v.main_link ? `<a class="btn" target="_blank" rel="noopener" href="${esc(v.main_link)}">Mở URL bán ↗</a>` : `<span class="btn">Không có URL bán</span>`}
      <a class="btn" target="_blank" rel="noopener" href="${esc(v.ad_library_url)}">Xem trên Thư viện QC</a>
      <button ${act("dig", v.cid)}>⤓ Đào sâu</button>
      ${v.clone ? `<a class="btn" target="_blank" rel="noopener" href="${esc(v.clone.admin_url)}">✓ Đã clone · mở Shopify ↗</a>`
        : `<button class="primary" ${act("cloneVideo", v.cid)} ${v.clone_url ? "" : "disabled"}>⧉ Clone vào Shopify</button>`}
      <button ${act("downloadMedia", "video", v.cid, "video")} ${v.video_url ? "" : "disabled"}>⬇ Tải video</button>
      <button ${act("downloadMedia", "video", v.cid, "image")}>🖼 Tải ảnh</button>
      <button ${act("mark", v.cid, "test", !isTest)}>${isTest ? "✓ Đang test" : "+ Video test"}</button>
      <button ${act("mark", v.cid, "hidden", !isHidden)}>${isHidden ? "Bỏ ẩn" : "🙈 Ẩn video"}</button>
    </div>
    ${mediaNote(v.media)}
    <h3>Sức sống quảng cáo (đang chạy)</h3>
    <div class="boxes">
      <div class="box"><b class="green">${b.win}</b><small>Win · 7–14 ngày</small></div>
      <div class="box"><b style="color:var(--blue)">${b.scale}</b><small>Scale · dưới 7 ngày</small></div>
      <div class="box"><b>${b.old}</b><small>Cũ · trên 14 ngày</small></div></div>
    <div class="bar"><i class="o" style="width:${pct(b.old)}"></i><i class="w" style="width:${pct(b.win)}"></i><i class="s" style="width:${pct(b.scale)}"></i></div>
    <div class="note" style="display:flex;justify-content:space-between"><span><b style="color:#9ca3af">■</b> Cũ <b class="green">■</b> Win <b style="color:var(--blue)">■</b> Scale</span><span>${v.ads_gone} QC đã tắt</span></div>
    <h3>Tuổi thật</h3>
    <div class="kv"><span>Quảng cáo sớm nhất (mọi shop, cả QC đã tắt)</span><b>${fmtDate(v.first_ts)} · ${days(v.video_age_days)}</b></div>
    <div class="kv"><span>Trang bán tạo ngày${src}</span><b class="${v.page_old ? "red" : ""}">${v.landing_created_ts ? fmtDate(v.landing_created_ts) + " · " + days(v.landing_age_days) : "chưa rõ"}</b></div>
    <h3>POD</h3>
    <div class="kv"><span>Loại sản phẩm</span><b>${esc(v.product_type || "chưa rõ")}${v.personalized ? " · cá nhân hoá" : ""}</b></div>
    <div class="kv"><span>Niche</span><b>${v.niches && v.niches.length ? v.niches.map(n => `<a ${act("niche", n, false)}>${esc(n)}</a>`).join(", ") : "chưa rõ"}</b></div>
    ${v.pod_markers && v.pod_markers.length ? `<div class="kv"><span>App/nền tảng POD trên trang bán</span><b>${v.pod_markers.map(esc).join(", ")}</b></div>` : ""}
    ${v.product_videos > 1 ? `<div class="kv"><span>Cùng sản phẩm <small class="note">${esc(v.product_key)}</small></span>
      <b><a ${act("sameProduct", v.product_key)}>${v.product_videos} video →</a></b></div>` : ""}
    <h3>Thị trường</h3>
    <div class="kv"><span>Shop giữ quảng cáo sống 7–14 ngày<br><small class="note">${v.shops_new_post} shop đang lên bài mới</small></span><b>${v.shops_win} / ${v.shops_active}</b></div>
    <div class="kv"><span>Quảng cáo mỗi ngày<br><small class="note">${v.ads_total} QC từ ${fmtDate(v.first_ts)}</small></span><b>${v.ads_per_day}</b></div>
    <h3>Vì sao có nhãn này</h3>
    ${v.checks.map(c => `<div class="check">${c.ok === true ? "✅" : c.ok === false ? "❌" : "➖"} ${esc(c.text)}</div>`).join("")}
    ${(v.flag_checks || []).map(c => `<div class="check">${c.ok ? "✅" : "➖"} ${esc(c.text)}</div>`).join("")}
    ${histTable}
    ${v.price ? `<div class="kv"><span>Giá đang bán</span><b>$${esc(v.price)}${v.compare_price ? ` <s class="note">$${esc(v.compare_price)}</s>` : ""}</b></div>` : ""}
    ${sellList}
    ${sourcing}
    <h3>Theo dõi shop (${v.shop_list.length})</h3>
    <div>${v.shop_list.map(s => followBtn("shop", s.domain, s.domain, s.followed)).join("") || "—"}</div>
    <h3>Theo dõi page (${v.page_list.length})</h3>
    <div>${v.page_list.map(p => followBtn("page", p.id, p.name, p.followed)).join("") || "—"}</div>
    <h3>Các quảng cáo (${v.ads.length})</h3>
    <table><tr><th>Page</th><th>Bắt đầu</th><th>Trạng thái</th><th>Tải</th></tr>${v.ads.slice(0, 100).map(a =>
      `<tr><td><a target="_blank" rel="noopener" href="https://www.facebook.com/ads/library/?id=${esc(a.ad_id)}">${esc(a.page_name || a.page_id)}</a>
       ${a.collation_count > 1 ? `<small class="note">×${a.collation_count}</small>` : ""}</td>
       <td>${fmtDate(a.start_ts)}</td><td>${a.is_active ? '<span class="green">đang chạy</span>' : "đã tắt"}</td>
       <td>${a.video_url ? `<a ${act("downloadMedia", "ad", a.ad_id, "video")} title="Tải video của QC này">⬇</a>` : ""}
         ${a.thumb_url ? `<a ${act("downloadMedia", "ad", a.ad_id, "image")} title="Tải ảnh của QC này">🖼</a>` : ""}</td></tr>`).join("")}</table>`;
  $("#drawer").classList.remove("hidden");
}

function mediaNote(m) {
  if (!m || !m.video_url) return `<p class="note">QC này không có link video (QC ảnh) — vẫn tải được ảnh.</p>`;
  const extra = m.variants > 1 ? ` · ${m.variants} bản video khác nhau từ các shop (tải từng bản ở bảng Các quảng cáo bên dưới)` : "";
  if (m.video_expired) return `<p class="note red">Link video đã hết hạn lúc ${fmtTime(m.video_expires_ts)} — bấm Đào sâu hoặc quét lại để lấy link mới${extra}.</p>`;
  return m.video_expires_ts ? `<p class="note">Link video còn hạn tới ${fmtTime(m.video_expires_ts)} (Facebook đổi link định kỳ)${extra}.</p>`
    : extra ? `<p class="note">${extra.slice(3)}.</p>` : "";
}

function closeDrawer() { openCid = openVid = null; $("#drawer").classList.add("hidden");
  document.querySelectorAll(".row.on, .vrow.on").forEach(r => r.classList.remove("on")); }
async function dig(cid) { await post(`/api/videos/${enc(cid)}/dig`); pollJobs(); }

$("#logbar").onclick = e => { if (e.target.id !== "stopBtn") $("#log").classList.toggle("hidden"); };
$("#stopBtn").onclick = () => post("/api/stop");

let wasBusy = false, pollTimer = null;
async function pollJobs() {
  clearTimeout(pollTimer);
  try {
    const s = await api("/api/jobs");
    const busy = !!s.current;
    $("#current").textContent = busy ? `Đang chạy: ${s.current}` + (s.pending.length ? ` (+${s.pending.length} chờ)` : "")
      : (s.log.length ? s.log[s.log.length - 1].msg : "Chưa chạy việc nào");
    $("#stopBtn").classList.toggle("hidden", !busy);
    renderAlert(s.blocked);
    $("#log").textContent = s.log.map(l => new Date(l.ts * 1000).toLocaleTimeString() + "  " + l.msg).join("\n");
    const pp = $("#progress");
    if (pp) pp.innerHTML = progressPanel(s.progress);
    if (wasBusy && !busy) { render(); if (openCid) openDrawer(openCid); if (openVid) openSocial(openVid); }
    wasBusy = busy;
    pollTimer = setTimeout(pollJobs, busy ? 2000 : 8000);
  } catch { pollTimer = setTimeout(pollJobs, 8000); }
}

async function downloadDiag(name) {
  if (!IS_EXT) { location.href = `/api/diag/${enc(name)}/download`; return; }
  const {filename, base64} = await api(`/api/diag/${enc(name)}/download`);
  const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], {type: "application/zip"}));
  const a = Object.assign(document.createElement("a"), {href: url, download: filename});
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
async function loadDemo() {
  try { await post("/api/demo"); render(); } catch (e) { alert(e.message); }
}

const CHANGES = {product_type: el => filterBy("product_type", el.value), niche: el => filterBy("niche", el.value),
  pod: el => filterBy("pod", el.checked),
  viralPlatform: el => { viralFilters.platform = el.value; pageOffset = 0; render(); },
  viralSort: el => { viralFilters.sort = el.value; pageOffset = 0; render(); },
  viralMarket: el => { viralFilters.market = el.value; pageOffset = 0; render(); },
  passive: el => post("/api/passive", {enabled: el.checked}),
  kwMarket: el => { kwMarket = el.value; render(); }};
document.addEventListener("change", e => {
  const el = e.target.closest("[data-change]");
  if (el) CHANGES[el.dataset.change](el);
});

async function mark(cid, kind, on) {
  await post("/api/marks", {cid, kind, on});
  if (kind === "hidden" && on) closeDrawer(); else openDrawer(cid);
  render();
}
async function digBatch() {
  const r = await post("/api/dig/batch", {n: +($("#digN") || {}).value || 5});
  pollJobs(); alert(`Đã xếp ${r.queued} video vào hàng đào sâu.`);
}
async function sweepStores() {
  const r = await post("/api/stores/sweep", {n: +($("#sweepN") || {}).value || 10});
  pollJobs(); alert(`Đã xếp ${r.queued} store vào hàng soi.`); render();
}
async function sweepOne(domain) { await post("/api/stores/sweep", {domains: [domain]}); pollJobs(); }
function saveFile(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const a = Object.assign(document.createElement("a"), {href: url, download: name});
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
async function exportData() {
  const data = await api("/api/export");
  saveFile(`snakemedia-pod-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(data), "application/json");
}
async function importData() {
  const f = ($("#importFile") || {}).files && $("#importFile").files[0];
  if (!f) return alert("Chọn file .json đồng đội gửi trước đã");
  let data;
  try { data = JSON.parse(await f.text()); } catch { return alert("File không phải JSON hợp lệ"); }
  try {
    const r = await post("/api/import", data);
    pollJobs(); alert(`Đã gộp ${r.ads} QC mới và ${r.landings} trang bán. Đang chấm lại…`);
  } catch (e) { alert(e.message); }
}

async function scanTag(name, save) {
  const r = await post("/api/viral/scan", {platform: "tiktok", keywords: ["#" + name], save});
  pollJobs(); alert(r.queued ? `Đã xếp quét video #${name}${save ? " (tự quét mỗi đêm)" : ""}.` : "Hashtag này đang chờ quét.");
}

const ACTIONS = {cloneVideo, disconnectShopify, kwTab: k => { kwTab = k; render(); }, kwMarket: m => { kwMarket = m; render(); },
  refreshKwTrends, scanSelected, toggleAllKw, stopJobs: () => post("/api/stop").then(pollJobs), findChat, downloadDiag, loadDemo, setView, closeDrawer, runAll, clearScope: () => clearScope(),
  downloadMedia, batchMedia, scanTag, trendMarket: m => { trendMarket = m; render(); },
  mark, digBatch, sweepStores, sweepOne, exportData, importData,
  storeFilter: k => { storeFilter = k; pageOffset = 0; render(); },
  testNotify, clearToken, resumePlatform, openLogin, goSafety: () => setView("safety"), openSocial, removeViralKw, viralFilter: (k, val) => { viralFilters[k] = val; pageOffset = 0; render(); }, setLayout, goPage,
  sameProduct: (key) => { filters.product = key; filters.scopeName = "cùng sản phẩm " + key; closeDrawer(); setView("all"); }, showScope, toggleFollow, unfollow, scanFollow, scanKw, removeKw, dig, openDrawer,
  niche: (n, pod) => { filters.niche = n; if (pod) filters.pod = true; closeDrawer(); setView("all"); },
  fillKw: k => { $("#scanForm [name=keyword]").value = k; },
  copyText: t => navigator.clipboard.writeText(t).then(() => alert("Đã sao chép"), () => prompt("Sao chép:", t))};
document.addEventListener("click", e => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  e.stopPropagation();
  ACTIONS[el.dataset.act](...JSON.parse(el.dataset.args));
});

render(); pollJobs();
api("/api/info").then(i => { $("#ver").textContent = `SNAKEMEDIA POD v${i.version}`; }).catch(() => {});
