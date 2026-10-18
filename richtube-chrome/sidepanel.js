// ============================================================================
// RICHTUBE Spy - Side Panel: chạy Spy & hiển thị 3 cột (Tín hiệu · Giải mã · Sản xuất)
// ============================================================================

import { toMarkdown } from "./lib/export.js";
import { addToHistory, loadHistory, loadSettings, removeFromHistory } from "./lib/settings.js";
import { pushToEngine, spyVideo } from "./lib/spy.js";
import { parseVideoId } from "./lib/youtube.js";

const $ = (id) => document.getElementById(id);
const state = { settings: null, videoId: null, record: null, tab: "signal", busy: false };

// Dữ liệu từ YouTube/Gemini luôn được escape trước khi chèn vào trang
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmtNum = (n) => Number(n || 0).toLocaleString("en-US");

function setStatus(text, { error = false, spinning = false } = {}) {
  const el = $("status");
  if (!text) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.className = `status${error ? " error" : ""}`;
  el.innerHTML = `${spinning ? '<span class="spinner"></span> ' : ""}${esc(text)}`;
}

function setupProblem(s) {
  if (!s.geminiKeys.length) return "Chưa có Gemini API key. Bấm ⚙️ Cài đặt để nhập (bắt buộc).";
  return null;
}

// ------------------------------------------------------------------ Video hiện tại

async function detectCurrentVideo() {
  const fromQuery = new URLSearchParams(location.search).get("v"); // mở panel dạng tab để test
  let videoId = fromQuery ? parseVideoId(fromQuery) : null;
  if (!videoId && chrome.tabs) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url && /^https:\/\/(www\.)?youtube\.com\//.test(tab.url)) videoId = parseVideoId(tab.url);
  }
  state.videoId = videoId;
  renderCurrent();
}

function renderCurrent() {
  const info = $("current-info");
  const btn = $("spy-btn");
  const problem = setupProblem(state.settings);
  $("setup-hint").hidden = !problem;
  $("setup-hint").textContent = problem || "";

  if (!state.videoId) {
    info.textContent = "Mở một video YouTube (youtube.com/watch?v=...) để bắt đầu.";
    btn.disabled = true;
    return;
  }
  info.innerHTML = `<div class="video">
      <img src="https://i.ytimg.com/vi/${esc(state.videoId)}/mqdefault.jpg" alt="" />
      <div><div class="dim small">Video đang mở</div><div class="mono">${esc(state.videoId)}</div></div>
    </div>`;
  btn.disabled = state.busy || !!problem;
  btn.textContent = state.busy ? "⏳ Đang phân tích..." : "🔥 Spy video này";
}

// ------------------------------------------------------------------ Chạy Spy

async function runSpy(videoId) {
  if (state.busy || !videoId) return;
  const problem = setupProblem(state.settings);
  if (problem) {
    setStatus(problem, { error: true });
    return;
  }
  state.busy = true;
  renderCurrent();
  try {
    const record = await spyVideo(videoId, state.settings, {
      onProgress: (text) => setStatus(text, { spinning: true }),
    });
    await addToHistory(record);
    showRecord(record);
    setStatus("✅ Phân tích xong!");
    if (state.settings.engineUrl && state.settings.autoPush) await sendToEngine();
  } catch (err) {
    setStatus(`❌ ${err.message || err}`, { error: true });
  } finally {
    state.busy = false;
    renderCurrent();
    renderHistory();
  }
}

async function sendToEngine() {
  const s = state.settings;
  if (!state.record) return;
  if (!s.engineUrl) {
    setStatus("Chưa nhập địa chỉ Engine trong Cài đặt.", { error: true });
    return;
  }
  setStatus("Đang gửi về RICHTUBE Engine...", { spinning: true });
  try {
    const saved = await pushToEngine(state.record, s);
    state.record = saved;
    await addToHistory(saved);
    renderResult();
    setStatus(
      saved.lark_synced
        ? `✅ Đã gửi về Engine & đồng bộ Lark Base (${saved.lark_record_id}).`
        : "✅ Đã gửi về Engine (Dashboard + Telegram)."
    );
  } catch (err) {
    setStatus(`⚠️ Không gửi được về Engine: ${err.message || err}`, { error: true });
  }
}

// ------------------------------------------------------------------ Hiển thị kết quả

function showRecord(record) {
  state.record = record;
  state.tab = state.tab || "signal";
  renderResult();
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function chartSvg(curve, duration, spikes, drops) {
  if (!curve || curve.length < 2) {
    return '<div class="empty">Video chưa có dữ liệu Most Replayed (video mới hoặc ít lượt xem).</div>';
  }
  const W = 100;
  const H = 32;
  const toSec = (ts) => ts.trim().split(":").reduce((a, p) => a * 60 + Number(p || 0), 0);
  const range = (r) => r.split("-").map(toSec);
  const total = duration > 0 ? duration : Math.max(1, ...[...spikes, ...drops].map((p) => range(p.time_range)[1]));
  const step = W / (curve.length - 1);
  const pts = curve.map((v, i) => `${(i * step).toFixed(2)},${(H - v * (H - 2)).toFixed(2)}`);
  const line = `M${pts.join(" L")}`;
  const band = (p, color, op) => {
    const [a, b] = range(p.time_range);
    const x = Math.min((a / total) * W, W);
    const w = Math.max(Math.min((b / total) * W, W) - x, 0.8);
    return `<rect x="${x}" y="0" width="${w}" height="${H}" fill="${color}" opacity="${op}"/>`;
  };
  const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Biểu đồ sóng giữ chân">
      <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#34d399" stop-opacity=".55"/><stop offset="1" stop-color="#34d399" stop-opacity=".03"/></linearGradient></defs>
      ${spikes.map((p) => band(p, "#34d399", 0.12)).join("")}${drops.map((p) => band(p, "#ef4444", 0.2)).join("")}
      <path d="${line} L${W},${H} L0,${H} Z" fill="url(#g)"/><path d="${line}" fill="none" stroke="#34d399" stroke-width=".6" vector-effect="non-scaling-stroke"/>
    </svg></div><div class="axis"><span>00:00</span><span>${fmt(total / 2)}</span><span>${fmt(total)}</span></div>`;
}

function copyLine(text, label = "Copy") {
  return `<button class="copy-btn" data-copy="${esc(text)}">📋 ${label}</button>`;
}

function renderSignal(r) {
  const peaks = r.heatmap_peaks;
  return `<section class="card">
      <h3 class="green">🔥 Most Replayed Heatmap</h3>
      ${chartSvg(r.heatmap_curve, r.duration_seconds, peaks.retention_spikes, peaks.retention_drops)}
      ${peaks.retention_spikes.map((p) => `<div class="point"><div class="head"><span class="mono green">[${esc(p.time_range)}]</span><span class="green">Đỉnh ${Math.round(p.intensity * 100)}%</span></div><div class="small">${esc(p.note)}</div></div>`).join("")}
      ${peaks.retention_drops.map((p) => `<div class="point drop"><div class="head"><span class="mono red">[${esc(p.time_range)}]</span><span class="red">⚠ Vùng trũng ${Math.round(p.intensity * 100)}%</span></div><div class="small">${esc(p.note)}</div></div>`).join("")}
    </section>`;
}

function renderAnatomy(r) {
  const d = r.deconstruction;
  const pa = d.packaging_analysis;
  const hk = d.hook_30s_breakdown;
  const gp = d.exploitable_gaps;
  return `<section class="card kv">
      <h3 class="cyan">🎬 Mổ xẻ 30s đầu & Bao bì</h3>
      <p><strong>Đòn tâm lý:</strong> <span class="amber">${esc(pa.psychological_angle)}</span></p>
      <p><strong>Kích thích thị giác:</strong> ${esc(pa.visual_trigger)}</p>
      <p><strong>Khoảng trống tò mò:</strong> ${esc(pa.curiosity_gap)}</p>
      <p><strong>Cơ chế 5s đầu:</strong> ${esc(hk.opening_mechanism)}</p>
      <p><strong>Nhịp dựng & Âm thanh:</strong> <span class="green">${esc(hk.pacing_notes)}</span></p>
      <p><strong>Vòng lặp tò mò:</strong> ${esc(hk.core_loop_opened)}</p>
      ${d.narrative_beats.map((b) => `<div class="beat"><div class="row"><span class="mono cyan">[${esc(b.time_range)}]</span><span class="spacer"></span><span class="dim small">${esc(b.retention_technique)}</span></div><b>${esc(b.beat_name)}</b><div class="muted small">${esc(b.structural_purpose)}</div></div>`).join("")}
    </section>
    <section class="card gap-card">
      <h3 class="amber">💡 Vũ khí vượt mặt đối thủ</h3>
      <div>${esc(gp.superior_angle_proposal)}</div>
      <p class="small"><strong>Tranh cãi:</strong> ${esc(gp.viewer_complaints_or_debates)}</p>
      <ul class="small">${gp.unanswered_questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>
    </section>`;
}

function renderProduction(r) {
  const pb = r.blueprint.packaging_blueprint;
  return `<section class="card">
      <h3 class="green">🏷️ Tiêu đề đề xuất</h3>
      ${pb.titles.map((t, i) => `<div class="copy-line"><b>${i + 1}. ${esc(t)}</b>${copyLine(t)}</div>`).join("")}
      ${pb.thumbnail_concepts.map((tc) => `<div class="copy-line" style="display:block"><div class="row"><b class="cyan">🎨 Prompt Thumbnail</b><span class="spacer"></span>${copyLine(tc.ai_image_prompt)}</div><div class="muted small">${esc(tc.layout_description)}</div><div class="prompt">${esc(tc.ai_image_prompt)}</div></div>`).join("")}
    </section>
    <section class="card">
      <h3>🎞️ Kịch bản phân cảnh 4 cột</h3>
      ${r.blueprint.production_script.map((s) => `<div class="scene">
          <div class="head"><span class="tag">Cảnh #${esc(s.scene_id)}</span><span class="mono small">${esc(s.estimated_time)}</span><span class="spacer"></span><span class="cyan small">${esc(s.beat_function)}</span></div>
          <div class="label green">🎙️ Lời thoại</div><div>${esc(s.voiceover_script)}</div>
          <div class="label cyan">🎬 Dựng hình</div><div class="muted">${esc(s.visual_direction)}</div>
          <div class="label purple row">🖼️ Visual AI Prompt <span class="spacer"></span>${copyLine(s.visual_generation_prompt)}</div><div class="prompt">${esc(s.visual_generation_prompt)}</div>
          <div class="sfx">🔊 ${esc(s.audio_sfx_cues)}</div>
        </div>`).join("")}
    </section>`;
}

function renderResult() {
  const r = state.record;
  const el = $("result");
  if (!r) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const tabs = [["signal", "1. Tín hiệu"], ["anatomy", "2. Giải mã"], ["production", "3. Sản xuất"]];
  const body = state.tab === "anatomy" ? renderAnatomy(r) : state.tab === "production" ? renderProduction(r) : renderSignal(r);
  el.innerHTML = `
    <section class="card">
      <div class="video">
        <img src="${esc(r.thumbnail_url)}" alt="" />
        <div><div class="title">${esc(r.title)}</div><div class="muted small">[${esc(r.market)}] ${esc(r.channel_name)} · ${esc(r.published_hours_ago)}h trước</div></div>
      </div>
      <div class="metrics">
        <div class="metric"><span>TAE</span><b>${r.tae_score ? `<span class="tae">${esc(r.tae_score)}x</span>` : '<span class="dim small">cần API key</span>'}</b></div>
        <div class="metric"><span>VPH</span><b class="green">${fmtNum(r.current_vph)}</b></div>
        <div class="metric"><span>Baseline</span><b>${r.baseline_vph ? fmtNum(r.baseline_vph) : "—"}</b></div>
      </div>
      <div class="row" style="margin-top:10px">
        <button class="btn" data-action="copy-md">📋 Copy kịch bản</button>
        <button class="btn" data-action="download-md">⬇️ Tải .md</button>
        ${state.settings.engineUrl ? `<button class="btn" data-action="push">📤 ${r.lark_synced ? "Gửi lại" : "Gửi"} Engine/Lark</button>` : ""}
        <a class="btn" href="${esc(r.url)}" target="_blank" rel="noreferrer">↗ Xem gốc</a>
      </div>
    </section>
    <nav class="tabs" style="margin-top:12px">${tabs.map(([k, label]) => `<button data-tab="${k}" class="${state.tab === k ? "active" : ""}">${label}</button>`).join("")}</nav>
    <div style="margin-top:12px; display:grid; gap:12px">${body}</div>`;
}

async function renderHistory() {
  const history = await loadHistory();
  $("history").innerHTML = history.length
    ? history.map((r) => `<div class="history-item" data-open="${esc(r.video_id)}">
          <img src="${esc(r.thumbnail_url)}" alt="" />
          <div style="flex:1"><div class="t">${esc(r.title)}</div><div class="dim small">${r.tae_score ? `TAE ${esc(r.tae_score)}x · ` : ""}${new Date(r.analyzed_at).toLocaleString("vi-VN")}</div></div>
          <button class="copy-btn" data-remove="${esc(r.video_id)}" title="Xoá khỏi lịch sử">✕</button>
        </div>`).join("")
    : '<div class="empty">Chưa có video nào. Mở một video YouTube và bấm 🔥 Spy.</div>';
}

// ------------------------------------------------------------------ Sự kiện

function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    setStatus("📋 Đã copy!");
  } catch {
    setStatus("Trình duyệt chặn quyền copy.", { error: true });
  }
}

document.addEventListener("click", async (e) => {
  const t = e.target.closest("[data-copy],[data-tab],[data-action],[data-open],[data-remove]");
  if (!t) return;
  if (t.dataset.copy !== undefined) return copy(t.dataset.copy);
  if (t.dataset.tab) {
    state.tab = t.dataset.tab;
    return renderResult();
  }
  if (t.dataset.remove) {
    e.stopPropagation();
    await removeFromHistory(t.dataset.remove);
    return renderHistory();
  }
  if (t.dataset.open) {
    const r = (await loadHistory()).find((x) => x.video_id === t.dataset.open);
    if (r) showRecord(r);
    return;
  }
  const action = t.dataset.action;
  if (action === "copy-md") return copy(toMarkdown(state.record));
  if (action === "download-md") return download(`richtube-${state.record.video_id}.md`, toMarkdown(state.record));
  if (action === "push") return sendToEngine();
});

$("spy-btn").addEventListener("click", () => runSpy(state.videoId));
$("open-options").addEventListener("click", () => chrome.runtime.openOptionsPage());

chrome.tabs?.onActivated.addListener(detectCurrentVideo);
chrome.tabs?.onUpdated.addListener((_id, change) => change.url && detectCurrentVideo());

async function takePendingSpy() {
  const { pendingSpy } = await chrome.storage.session.get("pendingSpy");
  if (pendingSpy && Date.now() - pendingSpy.at < 60_000) {
    await chrome.storage.session.remove("pendingSpy");
    state.videoId = pendingSpy.videoId;
    renderCurrent();
    runSpy(pendingSpy.videoId);
  }
}

chrome.storage.onChanged.addListener(async (changes, area) => {
  if (area === "session" && changes.pendingSpy?.newValue) takePendingSpy();
  if (area === "local" && changes.settings) {
    state.settings = await loadSettings();
    renderCurrent();
  }
});

(async function init() {
  state.settings = await loadSettings();
  await detectCurrentVideo();
  await renderHistory();
  await takePendingSpy();
})();
