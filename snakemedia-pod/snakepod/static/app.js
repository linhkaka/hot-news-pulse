const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const api = (p, o) => fetch(p, o).then(async r => {
  if (!r.ok) { let m = r.status; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
});
const post = (p, body) => api(p, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
const del = p => api(p, {method: "DELETE"});
const days = d => d == null ? "?" : `${Math.round(d)} ngày`;
const fmtDate = ts => ts ? new Date(ts * 1000).toISOString().slice(0, 10) : "?";
const ago = ts => { if (!ts) return "chưa"; const s = Date.now() / 1000 - ts;
  return s < 3600 ? `${Math.max(1, Math.round(s / 60))} phút trước` : s < 86400 ? `${Math.round(s / 3600)} giờ trước` : `${Math.round(s / 86400)} ngày trước`; };
const thumb = v => v.thumb ? `/thumbs/${encodeURIComponent(v.thumb)}` : (v.thumb_url || "");
const enc = encodeURIComponent;
// Nút bấm mang dữ liệu trong data-args (JSON) thay vì nhúng vào mã JS: tên page/shop có dấu nháy cũng an toàn
const act = (name, ...args) => `data-act="${name}" data-args="${esc(JSON.stringify(args))}"`;
const LABEL = {sap_win: ["Sắp WIN", "p"], win: ["Video Win", "g"], scale: ["Video scale", ""], theo_doi: ["Chờ thêm dữ liệu", ""],
  trang_cu: ["Trang bán cũ", "r"], cu: ["Video già", "r"]};
const TITLES = {overview: "Tổng quan", scan: "Quét từ khoá", all: "Tất cả video", niches: "Niche POD",
  follows: "Theo dõi đặc biệt", keywords: "Tự quét mỗi đêm", shops: "Kho shop"};
const DATE_SOURCE = {api: "dữ liệu sản phẩm", uuid: "ước tính từ mã sản phẩm", anh: "ước tính từ ảnh sản phẩm"};
const POD_KEYWORDS = ["personalized dog shirt", "custom name mug", "personalized ornament", "nurse shirt", "teacher mug",
  "grandma sweatshirt", "memorial canvas", "custom pet portrait", "fishing shirt", "veteran flag", "halloween doormat",
  "christmas blanket"];

let view = location.hash.slice(1) || "overview", openCid = null;
// Bộ lọc dùng chung cho các màn hình danh sách video
const filters = {product_type: "", niche: "", pod: false, page_id: "", shop: "", scopeName: ""};

function setView(v) { view = v; location.hash = v; render(); }
document.querySelectorAll("#nav a").forEach(a => a.onclick = () => { clearScope(false); setView(a.dataset.view); });
window.onhashchange = () => { const v = location.hash.slice(1); if (v && v !== view) { view = v; render(); } };
let t; $("#search").oninput = () => { clearTimeout(t); t = setTimeout(render, 250); };

function clearScope(rerender = true) { filters.page_id = filters.shop = filters.scopeName = ""; if (rerender) render(); }
function showScope(kind, key, name) {
  filters.page_id = kind === "page" ? key : ""; filters.shop = kind === "shop" ? key : "";
  filters.scopeName = name || key; setView("all");
}
function filterBy(key, value) { filters[key] = value; if (!LABEL[view] && view !== "all") setView("all"); else render(); }

async function refreshCounts() {
  const s = await api("/api/stats");
  for (const l of s.labels) document.querySelector(`[data-count=${l.key}]`).textContent = l.count;
  document.querySelector("[data-count=all]").textContent = s.total;
  api("/api/autoscan").then(a => { $("#cnt-follows").textContent = a.follows; $("#cnt-keywords").textContent = a.keywords; });
  return s;
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
  parts.push(`video ${days(v.video_age_days)}`);
  if (v.landing_age_days != null) parts.push(`<span class="${v.page_old ? "red" : ""}">URL ${days(v.landing_age_days)}${v.landing_date_source && v.landing_date_source !== "api" ? "*" : ""}</span>`);
  parts.push(`${v.pages_active}/${v.pages_total} page`, `${v.shops_active}/${v.shops_total} shop`, `${v.ads_per_day} QC/ngày`);
  return parts.join(" · ") + podChips(v) + (v.platform ? `<span class="chip">${esc(v.platform)}</span>` : "");
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
    ${filters.scopeName ? `<span class="scope">Đang xem: <b>${esc(filters.scopeName)}</b><a onclick="clearScope()">✕ bỏ</a></span>` : ""}
    <select onchange="filterBy('product_type', this.value)"><option value="">Mọi loại sản phẩm</option>${opt(facets.product_types, filters.product_type)}</select>
    <select onchange="filterBy('niche', this.value)"><option value="">Mọi niche</option>${opt(facets.niches, filters.niche)}</select>
    <label><input type="checkbox" ${filters.pod ? "checked" : ""} onchange="filterBy('pod', this.checked)"> Chỉ POD</label>
  </div>`;
}

async function renderList(label) {
  const p = new URLSearchParams();
  const q = $("#search").value.trim();
  if (label) p.set("label", label);
  if (q) p.set("q", q);
  for (const k of ["product_type", "niche", "page_id", "shop"]) if (filters[k]) p.set(k, filters[k]);
  if (filters.pod) p.set("pod", "true");
  const {items, facets} = await api("/api/videos?" + p);
  const bar = filterBar(facets);
  if (!items.length) return bar + `<div class="list"><div class="empty">Chưa có video nào ở mục này.<br>Vào <a onclick="setView('scan')"><b>Quét từ khoá</b></a> để bắt đầu.</div></div>`;
  return bar + `<div class="list">${items.map(row).join("")}</div>`;
}

async function renderOverview() {
  const [s, auto, niches] = await Promise.all([refreshCounts(), api("/api/autoscan"), api("/api/niches")]);
  const cards = s.labels.filter(l => l.key !== "theo_doi").map(l => `<a class="card" onclick="setView('${l.key}')"><div class="big">${l.count}</div>${l.name}</a>`).join("");
  const topN = niches.filter(n => n.sap_win + n.win + n.scale).slice(0, 6);
  return `<div class="cards">${cards}</div>
    <div class="cards">
      <a class="card" onclick="setView('keywords')"><div class="note">Tự quét mỗi đêm</div>
        <b>${auto.enabled ? `Bật · ${auto.hour}h` : "Đang tắt"}</b><div class="note">${auto.keywords} từ khoá · ${auto.follows} page/shop<br>Lần gần nhất: ${auto.last_date || "chưa"}</div></a>
      <a class="card" style="grid-column:span 2" onclick="setView('niches')"><div class="note">Niche POD đang nóng</div>
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
    Các ngưỡng sửa trong <code>snakepod/config.py</code>, từ khoá POD/niche sửa trong <code>snakepod/pod.py</code>.</div></div>
    <h3>Lượt quét gần đây</h3>${scansTable(s.scans)}`;
}

function scansTable(scans) {
  if (!scans.length) return `<div class="note">Chưa quét lần nào.</div>`;
  return `<div class="list"><table><tr><th>Việc</th><th>Trạng thái</th><th>Số QC</th><th>Bắt đầu</th></tr>${scans.map(s =>
    `<tr><td>${esc(s.target)}</td><td>${esc(s.status)}${s.error ? ` <span class="red" title="${esc(s.error)}">(lỗi)</span>` : ""}</td>
     <td>${s.n_ads}</td><td>${ago(s.started_ts)}</td></tr>`).join("")}</table></div>`;
}

async function renderScan() {
  const scans = await api("/api/scans");
  return `<form class="scan" id="scanForm">
      <input name="keyword" placeholder="Từ khoá, vd: personalized dog shirt, nurse mug…" required>
      <input name="country" value="US" size="3" title="Mã quốc gia">
      <input name="max_ads" type="number" value="300" style="width:90px" title="Số QC tối đa">
      <label class="note"><input type="checkbox" name="save" checked> Lưu để tự quét mỗi đêm</label>
      <button class="primary">Quét</button></form>
    <div class="note">Gợi ý từ khoá POD (bấm để điền):</div>
    <div class="chips">${POD_KEYWORDS.map(k => `<span class="chip" ${act("fillKw", k)}>${esc(k)}</span>`).join("")}</div>
    <p class="note">Tool mở cửa sổ Chromium, vào Thư viện quảng cáo Facebook, cuộn và đọc QC video (cả QC đã tắt).
    Sau đó tải thumbnail để gom QC trùng video, đọc tuổi trang bán, nhận diện POD, rồi chấm lại. Có thể xếp hàng nhiều từ khoá.</p>
    ${scansTable(scans)}`;
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
        <select name="hour">${hours}</select><button class="small">Lưu</button>
        <button type="button" class="primary small" onclick="runAll()">Quét tất cả ngay</button>
      </form>
      <p class="note" style="margin-bottom:0">Mỗi đêm tool quét lại ${auto.keywords} từ khoá dưới đây và ${auto.follows} page/shop ở
      <a onclick="setView('follows')">Theo dõi đặc biệt</a>. Lần gần nhất: ${auto.last_date || "chưa"}.
      <b>Tool phải đang mở</b> (máy không tắt/ngủ) vào giờ đó. Bản cài đặt có tuỳ chọn "Tự mở cùng Windows".</p></div>
    <form class="toolbar" id="kwForm"><input name="keyword" placeholder="Thêm từ khoá…" required style="flex:1;min-width:200px">
      <input name="country" value="US" size="3"><button class="small">+ Thêm</button></form>
    ${kws.length ? `<div class="list"><table><tr><th>Từ khoá</th><th>Quốc gia</th><th>Quét lần cuối</th><th></th></tr>
      ${kws.map(k => `<tr><td><b>${esc(k.keyword)}</b></td><td>${esc(k.country)}</td><td>${ago(k.last_scan_ts)}</td>
        <td><button class="small" ${act("scanKw", k.keyword, k.country)}>Quét</button>
            <button class="small" ${act("removeKw", k.keyword)}>Xoá</button></td></tr>`).join("")}</table></div>`
      : `<div class="empty">Chưa có từ khoá nào.</div>`}`;
}

async function renderShops() {
  const rows = await api("/api/shops");
  if (!rows.length) return `<div class="empty">Chưa có shop nào. Hãy quét vài từ khoá trước.</div>`;
  return `<p class="note">Mọi shop (domain trang bán) tool từng thấy. Bấm + để theo dõi (★ = đang theo dõi), bấm tên để xem video của shop.</p>
    <div class="list"><table><tr><th></th><th>Shop</th><th>Nền tảng</th><th class="num">QC đang chạy</th><th class="num">Page</th>
    <th class="num">Video</th><th class="num">Sắp WIN/Win</th><th>QC đầu tiên</th><th>QC mới nhất</th></tr>
    ${rows.map(r => `<tr><td><button class="follow ${r.followed ? "on" : ""}" ${act("toggleFollow", "shop", r.domain, r.domain, r.followed)} title="${r.followed ? "Bỏ theo dõi" : "Theo dõi"}">${r.followed ? "★" : "+"}</button></td>
      <td><a ${act("showScope", "shop", r.domain, r.domain)}><b>${esc(r.domain)}</b></a>${r.pod ? '<span class="chip o">POD</span>' : ""}</td>
      <td>${esc(r.platform || "?")}${r.pod_markers ? ` <small class="note">${esc(r.pod_markers)}</small>` : ""}</td>
      <td class="num">${r.active || 0}/${r.ads}</td><td class="num">${r.pages}</td><td class="num">${r.videos}</td>
      <td class="num ${r.hot ? "green" : ""}">${r.hot}</td><td>${fmtDate(r.first_ts)}</td><td>${fmtDate(r.last_ts)}</td></tr>`).join("")}</table></div>`;
}

const VIEWS = {overview: renderOverview, scan: renderScan, niches: renderNiches, follows: renderFollows,
  keywords: renderKeywords, shops: renderShops};

async function render() {
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.view === view));
  $("#title").textContent = TITLES[view] || (LABEL[view] || [view])[0];
  $("#search").classList.toggle("hidden", !!VIEWS[view]);
  let html;
  try {
    html = VIEWS[view] ? await VIEWS[view]() : await renderList(view === "all" ? null : view);
  } catch (e) { html = `<div class="empty">Lỗi tải dữ liệu: ${esc(e.message)}</div>`; }
  $("#content").innerHTML = html;
  document.querySelectorAll(".row").forEach(r => r.onclick = () => openDrawer(r.dataset.cid));
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
  on("#autoForm", async d => { await post("/api/autoscan", {enabled: !!d.enabled, hour: +d.hour}); render(); });
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
  openCid = cid;
  document.querySelectorAll(".row").forEach(r => r.classList.toggle("on", r.dataset.cid === cid));
  const v = await api(`/api/videos/${enc(cid)}`);
  const [ln, cls] = LABEL[v.label] || [v.label, ""];
  const b = v.buckets, tot = Math.max(1, b.old + b.win + b.scale);
  const pct = n => (100 * n / tot).toFixed(1) + "%";
  const img = thumb(v) ? `<img class="hero" src="${esc(thumb(v))}">` : `<div class="hero"></div>`;
  const src = v.landing_date_source ? ` <small class="note">(${DATE_SOURCE[v.landing_date_source] || v.landing_date_source})</small>` : "";
  const followBtn = (kind, key, name, on) =>
    `<button class="follow ${on ? "on" : ""}" ${act("toggleFollow", kind, key, name, on)} title="${on ? "Bỏ theo dõi" : "Theo dõi"}">${on ? "★" : "+"} ${esc(name)}</button>`;
  $("#drawer").innerHTML = `<button class="x" onclick="closeDrawer()">✕</button>${img}
    <h2>${esc(v.title)}</h2>
    <div><span class="chip ${cls}">${ln}</span>${podChips(v)}${v.platform ? `<span class="chip">${esc(v.platform)}</span>` : ""}
      <span class="note"> · ${v.pages_total} Trang · ${v.shops_total} shop · quét ${ago(v.last_seen)}</span></div>
    <div class="btns">
      <a class="btn primary" target="_blank" rel="noopener" href="${esc(v.video_url || v.ad_library_url)}">▶ Xem video</a>
      ${v.main_link ? `<a class="btn" target="_blank" rel="noopener" href="${esc(v.main_link)}">Mở URL bán ↗</a>` : `<span class="btn">Không có URL bán</span>`}
      <a class="btn" target="_blank" rel="noopener" href="${esc(v.ad_library_url)}">Xem trên Thư viện QC</a>
      <button ${act("dig", v.cid)}>⤓ Đào sâu</button>
    </div>
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
    <h3>Thị trường</h3>
    <div class="kv"><span>Shop giữ quảng cáo sống 7–14 ngày<br><small class="note">${v.shops_new_post} shop đang lên bài mới</small></span><b>${v.shops_win} / ${v.shops_active}</b></div>
    <div class="kv"><span>Quảng cáo mỗi ngày<br><small class="note">${v.ads_total} QC từ ${fmtDate(v.first_ts)}</small></span><b>${v.ads_per_day}</b></div>
    <h3>Vì sao có nhãn này</h3>
    ${v.checks.map(c => `<div class="check">${c.ok === true ? "✅" : c.ok === false ? "❌" : "➖"} ${esc(c.text)}</div>`).join("")}
    <h3>Theo dõi shop (${v.shop_list.length})</h3>
    <div>${v.shop_list.map(s => followBtn("shop", s.domain, s.domain, s.followed)).join("") || "—"}</div>
    <h3>Theo dõi page (${v.page_list.length})</h3>
    <div>${v.page_list.map(p => followBtn("page", p.id, p.name, p.followed)).join("") || "—"}</div>
    <h3>Các quảng cáo (${v.ads.length})</h3>
    <table><tr><th>Page</th><th>Bắt đầu</th><th>Trạng thái</th></tr>${v.ads.slice(0, 100).map(a =>
      `<tr><td><a target="_blank" rel="noopener" href="https://www.facebook.com/ads/library/?id=${esc(a.ad_id)}">${esc(a.page_name || a.page_id)}</a>
       ${a.collation_count > 1 ? `<small class="note">×${a.collation_count}</small>` : ""}</td>
       <td>${fmtDate(a.start_ts)}</td><td>${a.is_active ? '<span class="green">đang chạy</span>' : "đã tắt"}</td></tr>`).join("")}</table>`;
  $("#drawer").classList.remove("hidden");
}

function closeDrawer() { openCid = null; $("#drawer").classList.add("hidden");
  document.querySelectorAll(".row.on").forEach(r => r.classList.remove("on")); }
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
    $("#log").textContent = s.log.map(l => new Date(l.ts * 1000).toLocaleTimeString() + "  " + l.msg).join("\n");
    if (wasBusy && !busy) { render(); if (openCid) openDrawer(openCid); }
    wasBusy = busy;
    pollTimer = setTimeout(pollJobs, busy ? 2000 : 8000);
  } catch { pollTimer = setTimeout(pollJobs, 8000); }
}

const ACTIONS = {showScope, toggleFollow, unfollow, scanFollow, scanKw, removeKw, dig, openDrawer,
  niche: (n, pod) => { filters.niche = n; if (pod) filters.pod = true; closeDrawer(); setView("all"); },
  fillKw: k => { $("#scanForm [name=keyword]").value = k; }};
document.addEventListener("click", e => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  e.stopPropagation();
  ACTIONS[el.dataset.act](...JSON.parse(el.dataset.args));
});

render(); pollJobs();
