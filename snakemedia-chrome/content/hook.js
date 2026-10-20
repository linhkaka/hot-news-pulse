// Chạy TRONG trang Facebook / TikTok (world MAIN), trước mọi script của trang.
// Sao chép phản hồi của các API dữ liệu QC / video (không sửa, không chặn) rồi chuyển cho content/agent.js.
// Chuyển cả phản hồi không có dữ liệu QC: khi Facebook đổi tên trường, gói chẩn đoán vẫn có cái để xem.
(() => {
  if (window.__snakepodHook) return;
  window.__snakepodHook = true;
  const PATTERNS = ["/api/graphql", "/api/search/", "/api/challenge/item_list", "/api/post/item_list", "creative_radar_api"];
  const MAX = 5e6;
  const want = u => { try { return PATTERNS.some(p => String(u).includes(p)); } catch { return false; } };
  const emit = (url, text) => {
    if (typeof text !== "string" || !text || text.length > MAX) return;
    document.dispatchEvent(new CustomEvent("snakepod-cap", {detail: JSON.stringify({url: String(url), text})}));
  };

  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    const p = origFetch.apply(this, arguments);
    try {
      const u = input instanceof Request ? input.url : String(input);
      if (want(u)) p.then(r => r.clone().text().then(t => emit(r.url || u, t))).catch(() => {});
    } catch {}
    return p;
  };

  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    try {
      if (want(url)) this.addEventListener("load", () => {
        try {
          const t = this.responseType === "" || this.responseType === "text" ? this.responseText
            : this.responseType === "json" ? JSON.stringify(this.response) : null;
          emit(this.responseURL || url, t);
        } catch {}
      });
    } catch {}
    return open.apply(this, arguments);
  };
})();
