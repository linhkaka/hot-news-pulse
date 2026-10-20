"""Chép giao diện dùng chung từ bản app sang tiện ích (1 nguồn, 2 nơi chạy).

    python snakemedia-chrome/sync_ui.py

Bài kiểm thử tests/test_ui.py::test_ui_matches_app báo lỗi nếu quên chạy.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent / "snakemedia-pod" / "snakepod" / "static"
FILES = {"app.js": "dashboard.js", "style.css": "style.css", "logo.png": "logo.png"}

if __name__ == "__main__":
    for src, dst in FILES.items():
        shutil.copyfile(STATIC / src, HERE / dst)
        print(f"{src} -> {dst}")
