// dHash: dấu vân tay 64 bit của ảnh thumbnail, để nhận ra cùng 1 video dù shop khác upload lại.

const gray = (r, g, b) => (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16;   // như Pillow convert("L")

// Thu ảnh về 9x8 ô xám (lấy trung bình từng ô 10x10 của ảnh 90x80) rồi so từng cặp ô cạnh nhau.
export function dhashBitmap(bmp) {
  const c = new OffscreenCanvas(90, 80);
  const ctx = c.getContext("2d", {willReadFrequently: true});
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bmp, 0, 0, 90, 80);
  const px = ctx.getImageData(0, 0, 90, 80).data;
  const cells = new Float64Array(72);
  for (let y = 0; y < 80; y++) for (let x = 0; x < 90; x++) {
    const i = (y * 90 + x) * 4;
    cells[Math.floor(y / 10) * 9 + Math.floor(x / 10)] += gray(px[i], px[i + 1], px[i + 2]);
  }
  let bits = 0n;
  for (let row = 0; row < 8; row++) for (let col = 0; col < 8; col++)
    bits = (bits << 1n) | (cells[row * 9 + col] > cells[row * 9 + col + 1] ? 1n : 0n);
  return bits.toString(16).padStart(16, "0");
}

export function popcount(x) {
  let n = 0;
  while (x) { x &= x - 1n; n++; }
  return n;
}

export const distance = (a, b) => popcount(BigInt("0x" + a) ^ BigInt("0x" + b));

function toDataUrl(buf, type) {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return `data:${type};base64,${btoa(s)}`;
}

// Ảnh nhỏ (cạnh dài <= 320px) để hiện trên giao diện, lưu luôn trong tiện ích vì link ảnh Facebook hết hạn.
export async function smallJpeg(bmp, max = 320) {
  const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const w = Math.max(1, Math.round(bmp.width * k)), h = Math.max(1, Math.round(bmp.height * k));
  const c = new OffscreenCanvas(w, h);
  const ctx = c.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bmp, 0, 0, w, h);
  const blob = await c.convertToBlob({type: "image/jpeg", quality: 0.8});
  return toDataUrl(await blob.arrayBuffer(), "image/jpeg");
}

// Tải ảnh -> [dhash, ảnh nhỏ dạng data URL]
export async function fetchImage(url, timeoutMs = 20000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {signal: ctl.signal, credentials: "omit"});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const bmp = await createImageBitmap(await r.blob());
    try { return [dhashBitmap(bmp), await smallJpeg(bmp)]; } finally { bmp.close(); }
  } finally {
    clearTimeout(timer);
  }
}
