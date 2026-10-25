"""Mở trình duyệt của tool để bạn đăng nhập Facebook hoặc TikTok 1 lần. Đóng cửa sổ khi xong."""
import sys

from playwright.sync_api import sync_playwright

from .scraper import open_browser

SITES = {
    "facebook": ("Facebook", "https://www.facebook.com/login"),
    "tiktok": ("TikTok", "https://www.tiktok.com/login"),
    "pinterest": ("Pinterest", "https://www.pinterest.com/login/"),
}


def main(site="facebook"):
    name, url = SITES[site]
    with sync_playwright() as p:
        ctx = open_browser(p, headless=False)
        page = ctx.new_page()
        page.goto(url)
        print(f"Đăng nhập {name} trong cửa sổ vừa mở, rồi ĐÓNG cửa sổ đó để lưu lại.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        ctx.close()
    print(f"Đã lưu phiên đăng nhập {name}.")


if __name__ == "__main__":
    main("tiktok" if "tiktok" in sys.argv[1:] else "facebook")
