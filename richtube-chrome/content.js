// ============================================================================
// RICHTUBE Spy - gắn nút "🔥 RICHTUBE Spy" dưới tiêu đề video YouTube
// ============================================================================

const BUTTON_ID = "richtube-spy-btn";

function currentVideoId() {
  const url = new URL(location.href);
  if (url.pathname === "/watch") return url.searchParams.get("v");
  const m = url.pathname.match(/^\/shorts\/([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

function toast(text) {
  document.getElementById("richtube-spy-toast")?.remove();
  const el = document.createElement("div");
  el.id = "richtube-spy-toast";
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

function ensureButton() {
  const videoId = currentVideoId();
  const existing = document.getElementById(BUTTON_ID);
  if (!videoId) {
    existing?.remove();
    return;
  }
  if (existing) return;
  const anchor = document.querySelector("#above-the-fold #title") || document.querySelector("ytd-watch-metadata #title");
  if (!anchor) return;

  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.type = "button";
  btn.textContent = "🔥 RICHTUBE Spy";
  btn.title = "Mổ xẻ video này: Heatmap, Hook 30s, lỗ hổng khán giả & kịch bản 4 cột";
  btn.addEventListener("click", () => {
    const id = currentVideoId();
    if (!id) return;
    chrome.runtime.sendMessage({ type: "richtube-spy", videoId: id }, (res) => {
      if (chrome.runtime.lastError || !res?.ok) {
        toast("Bấm biểu tượng RICHTUBE trên thanh công cụ Chrome để mở bảng phân tích.");
      }
    });
  });
  anchor.after(btn);
}

// YouTube là trang SPA: theo dõi khi chuyển video mà không tải lại trang
document.addEventListener("yt-navigate-finish", () => {
  document.getElementById(BUTTON_ID)?.remove();
  ensureButton();
});
let scheduled = false;
new MutationObserver(() => {
  if (scheduled) return; // YouTube thay đổi DOM liên tục -> gộp lại tối đa 1 lần/khung hình
  scheduled = true;
  requestAnimationFrame(() => {
    scheduled = false;
    ensureButton();
  });
}).observe(document.documentElement, { childList: true, subtree: true });
ensureButton();
