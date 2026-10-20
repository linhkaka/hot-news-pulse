// Tải ảnh / video của QC và video viral bằng trình tải của Chrome (lưu vào Tải về/SnakemediaPOD/<ngày>/).
//
// Link video Facebook (fbcdn) có hạn dùng: tham số `oe=` là thời điểm hết hạn (số giây, hệ 16).
// Link đã hết hạn thì phải quét lại / đào sâu để lấy link mới; ảnh thì còn bản lưu trong tiện ích.

export function linkExpiry(url) {
  try {
    const oe = new URL(url).searchParams.get("oe");
    if (!oe || !/^[0-9a-f]+$/i.test(oe)) return null;
    return parseInt(oe, 16);
  } catch { return null; }
}

export const expired = (url, now = Date.now() / 1000) => { const e = linkExpiry(url); return !!(e && e < now); };

export function slug(text, n = 50) {
  const s = String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s.slice(0, n).replace(/-+$/g, "") || "media";
}

function extOf(url, kind) {
  if (String(url).startsWith("data:image/png")) return ".png";
  if (String(url).startsWith("data:")) return ".jpg";
  const m = /\.(mp4|webm|jpe?g|png|webp)(?:$|\?)/i.exec(new URL(url).pathname);
  if (m) return "." + m[1].toLowerCase().replace("jpeg", "jpg");
  return kind === "video" ? ".mp4" : ".jpg";
}

const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

// Bắt đầu tải 1 file. local: ảnh đã lưu trong tiện ích (data URL) dùng khi link ảnh hỏng / hết hạn.
export async function download({url, local = null, kind, name}) {
  let src = url;
  if (!src || expired(src)) {
    if (kind === "image" && local) src = local;
    else if (!src) throw new Error(kind === "video" ? "QC này không có video" : "Không có ảnh");
    else throw new Error("Link đã hết hạn — quét lại / đào sâu để lấy link mới");
  }
  const filename = `SnakemediaPOD/${today()}/${name}${extOf(src, kind)}`;
  const id = await chrome.downloads.download({url: src, filename, conflictAction: "uniquify", saveAs: false});
  return {id, filename};
}
