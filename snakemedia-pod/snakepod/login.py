"""Mở trình duyệt của tool để bạn đăng nhập Facebook 1 lần. Đóng cửa sổ khi xong."""
from playwright.sync_api import sync_playwright

from .scraper import BASE, open_browser


def main():
    with sync_playwright() as p:
        ctx = open_browser(p, headless=False)
        page = ctx.new_page()
        page.goto("https://www.facebook.com/login")
        print("Đăng nhập Facebook trong cửa sổ vừa mở, rồi ĐÓNG cửa sổ đó để lưu lại.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        ctx.close()
    print("Đã lưu phiên đăng nhập. Thử mở:", BASE)


if __name__ == "__main__":
    main()
