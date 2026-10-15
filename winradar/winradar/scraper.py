"""Mở Thư viện quảng cáo Facebook bằng Chromium (Playwright), cuộn trang và đọc dữ liệu QC.

Dùng hồ sơ trình duyệt riêng (data/browser-profile) nên chỉ cần đăng nhập Facebook 1 lần
bằng "DangNhapFacebook.bat".
"""
import os
import random
from urllib.parse import unquote, urlencode, urlparse

from playwright.sync_api import sync_playwright

from . import config
from .fb_parser import parse_html, parse_json_text

BASE = "https://www.facebook.com/ads/library/"


def keyword_url(keyword, country):
    return BASE + "?" + urlencode({
        "active_status": "all", "ad_type": "all", "country": country, "is_targeted_country": "false",
        "media_type": "video", "q": keyword, "search_type": "keyword_unordered",
    })


def page_url(page_id, country):
    return BASE + "?" + urlencode({
        "active_status": "all", "ad_type": "all", "country": country, "is_targeted_country": "false",
        "media_type": "video", "search_type": "page", "view_all_page_id": page_id,
    })


def read_proxy():
    """Đọc proxy từ biến môi trường WINRADAR_PROXY hoặc dòng đầu tiên (không phải chú thích) của proxy.txt."""
    raw = os.environ.get("WINRADAR_PROXY", "").strip()
    if not raw and config.PROXY_FILE.exists():
        lines = [l.strip() for l in config.PROXY_FILE.read_text(encoding="utf-8-sig").splitlines()]
        raw = next((l for l in lines if l and not l.startswith("#")), "")
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    u = urlparse(raw)
    proxy = {"server": f"{u.scheme}://{u.hostname}:{u.port}" if u.port else f"{u.scheme}://{u.hostname}"}
    if u.username:
        proxy["username"] = unquote(u.username)
        proxy["password"] = unquote(u.password or "")
    return proxy


def launch_options(headless):
    """Chromium tự chọn (WINRADAR_CHROMIUM) hoặc Chromium đầy đủ do Playwright cài, kể cả khi chạy ẩn."""
    if config.CHROMIUM_PATH:
        return {"headless": headless, "executable_path": config.CHROMIUM_PATH}
    return {"headless": headless, "channel": "chromium"}


def open_browser(p, headless=None):
    config.BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    proxy = read_proxy()
    if proxy:
        print(f"Dùng proxy {proxy['server']}", flush=True)
    return p.chromium.launch_persistent_context(
        str(config.BROWSER_PROFILE),
        proxy=proxy,
        **launch_options(config.HEADLESS if headless is None else headless),
        locale="en-US",
        viewport={"width": 1366, "height": 900},
    )


def collect(ctx, url, max_ads, log, stop=lambda: False):
    """Mở 1 URL thư viện QC, cuộn tới khi đủ max_ads hoặc hết kết quả."""
    page = ctx.new_page()
    responses = []
    page.on("response", lambda r: responses.append(r) if "/api/graphql" in r.url else None)
    ads = {}

    def drain():
        while responses:
            r = responses.pop()
            try:
                text = r.text()
            except Exception:
                continue
            if "ad_archive_id" in text:
                for ad in parse_json_text(text):
                    ads[ad["ad_id"]] = ad

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        for ad in parse_html(page.content()):
            ads[ad["ad_id"]] = ad
        if "login" in page.url:
            log("Facebook bắt đăng nhập — chạy DangNhapFacebook.bat trước.")
        stale = 0
        while len(ads) < max_ads and stale < 5 and not stop():
            before = len(ads)
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(1500 + random.randint(0, 1200))
            drain()
            stale = stale + 1 if len(ads) == before else 0
            if len(ads) != before:
                log(f"  ... đã đọc {len(ads)} QC")
        drain()
    finally:
        page.close()
    return list(ads.values())[:max_ads]


def scan_keyword(keyword, country, max_ads, log, stop=lambda: False):
    with sync_playwright() as p:
        ctx = open_browser(p)
        try:
            return collect(ctx, keyword_url(keyword, country), max_ads, log, stop)
        finally:
            ctx.close()


def scan_pages(page_ids, country, max_ads, log, stop=lambda: False):
    out = []
    with sync_playwright() as p:
        ctx = open_browser(p)
        try:
            for pid in page_ids:
                if stop():
                    break
                log(f"Đào page {pid}")
                out += collect(ctx, page_url(pid, country), max_ads, log, stop)
        finally:
            ctx.close()
    return out
