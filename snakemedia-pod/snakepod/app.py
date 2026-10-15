"""Điểm khởi động của bản cài đặt SnakemediaPOD.exe.

  SnakemediaPOD.exe            chạy tool và mở trình duyệt
  SnakemediaPOD.exe --login    mở Chromium để đăng nhập Facebook
  SnakemediaPOD.exe --demo     chạy với dữ liệu giả (lưu riêng, không đụng dữ liệu thật)
  SnakemediaPOD.exe --data     mở thư mục dữ liệu (chứa proxy.txt)
  SnakemediaPOD.exe --selftest kiểm tra Chromium đi kèm có chạy được không
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROXY_TEMPLATE = (
    "# Proxy cho SNAKEMEDIA POD (tuy chon). Xoa dau # o 1 dong ben duoi va dien proxy cua ban:\n"
    "# http://user:pass@1.2.3.4:8080\n"
    "# socks5://1.2.3.4:1080\n"
)


def _port_in_use(host, port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _wait_and_open(url, host, port):
    for _ in range(60):
        if _port_in_use(host, port):
            webbrowser.open(url)
            return
        time.sleep(0.5)


def selftest():
    from playwright.sync_api import sync_playwright

    from .scraper import launch_options
    with sync_playwright() as p:
        b = p.chromium.launch(**launch_options(True))
        page = b.new_page()
        page.set_content("<title>ok</title>")
        title = page.title()
        b.close()
    print("SELFTEST OK" if title == "ok" else "SELFTEST FAIL")
    return 0 if title == "ok" else 1


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if getattr(sys, "frozen", False):
        # Chromium được đóng gói ngay trong thư mục cài đặt
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
    if "--demo" in args:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SnakemediaPOD-demo"
        os.environ["SNAKEPOD_DATA"] = str(base)

    from . import config  # import sau khi đã đặt biến môi trường

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not config.PROXY_FILE.exists():
        config.PROXY_FILE.write_text(PROXY_TEMPLATE, encoding="utf-8")

    if "--data" in args:
        os.startfile(config.DATA_DIR) if hasattr(os, "startfile") else print(config.DATA_DIR)
        return
    if "--selftest" in args:
        return selftest()
    if "--login" in args:
        from . import login
        login.main()
        return
    if "--demo" in args:
        from . import demo
        demo.main()

    url = f"http://{config.HOST}:{config.PORT}"
    if _port_in_use(config.HOST, config.PORT):
        print("SNAKEMEDIA POD đã đang chạy, mở trình duyệt...")
        webbrowser.open(url)
        return

    import uvicorn
    from .server import app

    print(f"SNAKEMEDIA POD đang chạy: {url}")
    print(f"Dữ liệu lưu tại: {config.DATA_DIR}")
    print("ĐÓNG CỬA SỔ NÀY để tắt tool.")
    if "--no-browser" not in args:
        threading.Thread(target=_wait_and_open, args=(url, config.HOST, config.PORT), daemon=True).start()
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    sys.exit(main())
