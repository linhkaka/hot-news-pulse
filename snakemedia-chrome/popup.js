const api = async (path, method = "GET", body = null) => {
  const r = await chrome.runtime.sendMessage({type: "api", method, path, body});
  if (!r || !r.ok) throw new Error((r && r.detail) || "Lỗi");
  return r.data;
};
const $ = s => document.querySelector(s);
const openDashboard = (hash = "") => chrome.tabs.create({url: chrome.runtime.getURL("dashboard.html" + hash)});

async function refresh() {
  try {
    const [stats, viral, jobs, passive] = await Promise.all([api("/api/stats"), api("/api/viral?limit=1"), api("/api/jobs"),
      api("/api/passive")]);
    const n = k => (stats.labels.find(l => l.key === k) || {}).count || 0;
    $("#n-sap").textContent = n("sap_win");
    $("#n-win").textContent = n("win");
    $("#n-viral").textContent = (viral.counts.dang_no || 0) + (viral.counts.viral || 0);
    const blocked = Object.values(jobs.blocked || {});
    $("#status").textContent = blocked.length ? "⚠ " + blocked[0].reason
      : jobs.current ? `Đang chạy: ${jobs.current}` + (jobs.pending.length ? ` (+${jobs.pending.length} chờ)` : "")
      : jobs.log.length ? jobs.log[jobs.log.length - 1].msg : "Chưa chạy việc nào";
    $("#passive").checked = passive.enabled;
  } catch (e) {
    $("#status").textContent = e.message;
  }
}

$("#scan").onsubmit = async e => {
  e.preventDefault();
  const keyword = e.target.keyword.value.trim();
  if (!keyword) return;
  await api("/api/scan", "POST", {keyword, country: "US", max_ads: 300, save: true});
  e.target.keyword.value = "";
  refresh();
};
$("#passive").onchange = e => api("/api/passive", "POST", {enabled: e.target.checked});
$("#open").onclick = () => openDashboard();
document.querySelectorAll(".nums a").forEach(a => a.onclick = e => { e.preventDefault(); openDashboard(new URL(a.href).hash); });

refresh();
setInterval(refresh, 3000);
