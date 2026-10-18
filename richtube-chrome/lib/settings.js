// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Cài đặt & lịch sử (lưu trong chrome.storage.local, chỉ trên máy bạn)
// ============================================================================

export const DEFAULTS = {
  youtubeApiKey: "",
  geminiKeys: [],
  geminiModel: "gemini-2.5-flash",
  watchVideo: true,
  titleLanguage: "English",
  scriptLanguage: "Tiếng Việt",
  engineUrl: "",
  engineApiKey: "",
  autoPush: true,
};

const HISTORY_LIMIT = 30;

export async function loadSettings() {
  const stored = await chrome.storage.local.get("settings");
  return { ...DEFAULTS, ...(stored.settings || {}) };
}

export async function saveSettings(settings) {
  await chrome.storage.local.set({ settings: { ...DEFAULTS, ...settings } });
}

export async function loadHistory() {
  const stored = await chrome.storage.local.get("history");
  return stored.history || [];
}

export async function addToHistory(record) {
  const history = (await loadHistory()).filter((r) => r.video_id !== record.video_id);
  history.unshift(record);
  await chrome.storage.local.set({ history: history.slice(0, HISTORY_LIMIT) });
}

export async function removeFromHistory(videoId) {
  const history = (await loadHistory()).filter((r) => r.video_id !== videoId);
  await chrome.storage.local.set({ history });
}
