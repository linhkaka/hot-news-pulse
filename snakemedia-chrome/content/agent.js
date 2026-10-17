// Cầu nối giữa trang (content/hook.js) và phần nền của tiện ích.
//  - chuyển các phản hồi API bắt được về phần nền;
//  - khi trang tải xong, gửi JSON nhúng sẵn trong trang (để "tự lưu khi lướt").
(() => {
  const MARKERS = ["ad_archive_id", "playCount", "ad_title", "play_count", "video_view_count"];
  const send = msg => { try { chrome.runtime.sendMessage(msg).catch(() => {}); } catch {} };

  document.addEventListener("snakepod-cap", e => {
    try {
      const {url, text} = JSON.parse(e.detail);
      send({type: "cap", url, text});
    } catch {}
  });

  document.addEventListener("DOMContentLoaded", () => {
    const texts = Array.from(document.querySelectorAll('script[type="application/json"]'), s => s.textContent || "")
      .filter(t => MARKERS.some(m => t.includes(m)));
    if (texts.length) send({type: "ssr", url: location.href, texts});
  });
})();
