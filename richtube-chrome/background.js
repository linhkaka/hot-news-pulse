// ============================================================================
// RICHTUBE Spy - Service Worker
// Bấm biểu tượng tiện ích hoặc nút "RICHTUBE Spy" trên YouTube -> mở Side Panel.
// ============================================================================

chrome.runtime.onInstalled.addListener((details) => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  if (details.reason === "install") chrome.runtime.openOptionsPage();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "richtube-spy" || !sender.tab) return;
  // Mở panel ngay trong lượt bấm của người dùng, rồi báo panel tự chạy Spy
  chrome.sidePanel
    .open({ tabId: sender.tab.id })
    .then(() => chrome.storage.session.set({ pendingSpy: { videoId: message.videoId, at: Date.now() } }))
    .then(() => sendResponse({ ok: true }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));
  return true; // trả lời bất đồng bộ
});
