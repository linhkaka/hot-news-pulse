// ============================================================================
// RICHTUBE Spy - Trang Cài đặt
// ============================================================================

import { loadSettings, saveSettings } from "./lib/settings.js";

const $ = (id) => document.getElementById(id);
const TEXT_FIELDS = ["youtubeApiKey", "geminiModel", "titleLanguage", "scriptLanguage", "engineUrl", "engineApiKey"];
const CHECK_FIELDS = ["watchVideo", "autoPush"];

async function fill() {
  const s = await loadSettings();
  for (const f of TEXT_FIELDS) $(f).value = s[f];
  for (const f of CHECK_FIELDS) $(f).checked = s[f];
  $("geminiKeys").value = s.geminiKeys.join("\n");
}

/** Engine trên VPS (không phải localhost) cần xin thêm quyền truy cập địa chỉ đó. */
async function ensureEnginePermission(url) {
  if (!url || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?/.test(url)) return true;
  const origin = `${new URL(url).origin}/*`;
  return chrome.permissions.request({ origins: [origin] });
}

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const settings = {};
  for (const f of TEXT_FIELDS) settings[f] = $(f).value.trim();
  for (const f of CHECK_FIELDS) settings[f] = $(f).checked;
  settings.geminiKeys = $("geminiKeys").value.split(/[\s,]+/).map((k) => k.trim()).filter(Boolean);
  settings.engineUrl = settings.engineUrl.replace(/\/+$/, "");

  try {
    if (!(await ensureEnginePermission(settings.engineUrl))) {
      $("saved").textContent = "⚠️ Bạn chưa cho phép truy cập địa chỉ Engine.";
      return;
    }
  } catch {
    $("saved").textContent = "⚠️ Địa chỉ Engine không hợp lệ.";
    return;
  }
  await saveSettings(settings);
  $("saved").textContent = "✅ Đã lưu! Mở một video YouTube và bấm 🔥 RICHTUBE Spy.";
});

fill();
