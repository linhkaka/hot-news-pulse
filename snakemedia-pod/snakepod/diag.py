"""Gói chẩn đoán: khi 1 lượt quét ra 0 kết quả / lỗi / gặp checkpoint, lưu lại những gì trang trả về
để người hỗ trợ sửa bộ đọc dữ liệu nhanh, không phải đoán.

Mỗi gói là 1 thư mục trong <dữ liệu>/diag: meta.json, page.html, responses.jsonl, screenshot.png.
Email trong dữ liệu được che (***@***). Trang có thể chứa tên tài khoản đang đăng nhập — xem trước khi gửi.
"""
import io
import json
import re
import shutil
import time
import zipfile

from . import config

KEEP = 15                     # giữ 15 gói gần nhất
MAX_RESPONSES = 40
MAX_RESPONSE_CHARS = 300_000
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _scrub(text):
    return _EMAIL_RE.sub("***@***", text or "")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "scan").lower()).strip("-")[:40] or "scan"


def directory():
    return config.DATA_DIR / "diag"


def save(label, url, final_url=None, html=None, responses=(), error=None, items=0, screenshot=None):
    """Lưu 1 gói, trả về tên gói."""
    root = directory()
    name = time.strftime("%Y%m%d-%H%M%S") + "_" + _slug(label)
    folder = root / name
    n = 1
    while folder.exists():
        n += 1
        folder = root / f"{name}-{n}"
    folder.mkdir(parents=True)
    meta = {"label": label, "url": url, "final_url": final_url, "error": error, "items": items,
            "responses": len(responses), "ts": int(time.time())}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if html:
        (folder / "page.html").write_text(_scrub(html), encoding="utf-8")
    with open(folder / "responses.jsonl", "w", encoding="utf-8") as f:
        for u, text in list(responses)[:MAX_RESPONSES]:
            f.write(json.dumps({"url": u, "body": _scrub(text[:MAX_RESPONSE_CHARS])}, ensure_ascii=False) + "\n")
    if screenshot:
        (folder / "screenshot.png").write_bytes(screenshot)
    _prune()
    return folder.name


def _prune():
    folders = sorted((p for p in directory().iterdir() if p.is_dir()), key=lambda p: p.name)
    for old in folders[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)


def list_bundles():
    root = directory()
    if not root.exists():
        return []
    out = []
    for p in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True):
        try:
            meta = json.loads((p / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        size = sum(f.stat().st_size for f in p.iterdir() if f.is_file())
        out.append({"name": p.name, "size": size, **meta})
    return out


def zip_bundle(name):
    """Nén 1 gói thành zip (bytes). Tên không hợp lệ -> None."""
    root = directory()
    existing = {p.name for p in root.iterdir() if p.is_dir()} if root.exists() else set()
    if name not in existing:          # chỉ nhận đúng tên gói đang có -> không đọc được file ngoài thư mục
        return None
    folder = root / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.iterdir():
            if f.is_file():
                z.write(f, f"{name}/{f.name}")
    return buf.getvalue()
