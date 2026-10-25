"""Mở Thư viện quảng cáo Facebook bằng Chromium (Playwright), cuộn trang và đọc dữ liệu QC.

Dùng hồ sơ trình duyệt riêng (data/browser-profile) nên chỉ cần đăng nhập Facebook 1 lần
bằng "DangNhapFacebook.bat".
"""
import os
import random
import re
import time
from urllib.parse import quote, unquote, urlencode, urlparse

from playwright.sync_api import sync_playwright

from . import config, diag, safety, social
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
    """Đọc proxy từ biến môi trường SNAKEPOD_PROXY hoặc dòng đầu tiên (không phải chú thích) của proxy.txt."""
    raw = os.environ.get("SNAKEPOD_PROXY", "").strip()
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
    """Chromium tự chọn (SNAKEPOD_CHROMIUM) hoặc Chromium đầy đủ do Playwright cài, kể cả khi chạy ẩn."""
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


def collect(ctx, url, max_ads, log, stop=lambda: False, *, match=lambda u: "/api/graphql" in u,
            marker="ad_archive_id", parse_text=parse_json_text, parse_page=parse_html, key="ad_id",
            noun="QC", platform="facebook", click_more=None, prepare=None, label=None, progress=None):
    """Mở 1 trang, cuộn tới khi đủ max_ads hoặc hết kết quả, đọc dữ liệu từ các phản hồi JSON của trang.

    Mặc định cho Thư viện QC Facebook; TikTok / Facebook Reels truyền bộ lọc và bộ đọc riêng.
    Gặp checkpoint / captcha / trang bắt đăng nhập -> ném safety.CheckpointError và dừng ngay.
    Ra 0 kết quả hoặc lỗi -> lưu gói chẩn đoán (diag.py) để sửa bộ đọc dữ liệu.
    """
    page = ctx.new_page()
    responses = []
    raws = []                     # phản hồi thô cho gói chẩn đoán
    page.on("response", lambda r: responses.append(r) if match(r.url) else None)
    items = {}

    def drain():
        while responses:
            r = responses.pop()
            try:
                text = r.text()
            except Exception:
                continue
            if len(raws) < diag.MAX_RESPONSES:
                raws.append((r.url, text))
            if any(m in text for m in ((marker,) if isinstance(marker, str) else marker)):
                for it in parse_text(text):
                    items[it[key]] = it

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        safety.check_page(platform, page)
        if prepare:
            prepare(page, log)
            page.wait_for_timeout(3000)
            safety.check_page(platform, page)
        for it in parse_page(page.content()):
            items[it[key]] = it
        drain()
        stale = rounds = 0
        lo, hi = config.SCROLL_PAUSE_MS
        while len(items) < max_ads and stale < 5 and rounds < config.MAX_SCROLL_ROUNDS and not stop():
            rounds += 1
            before = len(items)
            if click_more:
                try:
                    btn = page.locator(click_more).first
                    if btn.is_visible():
                        btn.click()
                except Exception:
                    pass
            page.mouse.wheel(0, random.randint(2500, 5000))
            page.wait_for_timeout(random.randint(lo, hi))
            safety.check_page(platform, page)
            drain()
            stale = stale + 1 if len(items) == before else 0
            if len(items) != before:
                log(f"  ... đã đọc {len(items)} {noun}")
                if progress:
                    progress(len(items))
        drain()
        if not items:
            _save_diag(page, label or f"{platform}-{noun}", url, raws, "Không đọc được kết quả nào", 0, log)
    except Exception as e:
        _save_diag(page, label or f"{platform}-{noun}", url, raws, str(e)[:500], len(items), log)
        raise
    finally:
        page.close()
    return list(items.values())[:max_ads]


def _save_diag(page, label, url, raws, error, n_items, log):
    try:
        html = page.content()
    except Exception:
        html = None
    try:
        shot = page.screenshot()
    except Exception:
        shot = None
    try:
        name = diag.save(label, url, page.url, html, raws, error, n_items, shot)
        log(f"  Đã lưu gói chẩn đoán '{name}' (mục Chế độ an toàn → Gói chẩn đoán)")
    except Exception as e:  # không để lỗi lưu chẩn đoán che lỗi thật
        log(f"  Không lưu được gói chẩn đoán: {e}")


def run_collect(url, max_items, log, stop=lambda: False, **kw):
    with sync_playwright() as p:
        ctx = open_browser(p)
        try:
            return collect(ctx, url, max_items, log, stop, **kw)
        finally:
            ctx.close()


def scan_keyword(keyword, country, max_ads, log, stop=lambda: False, progress=None):
    return run_collect(keyword_url(keyword, country), max_ads, log, stop, progress=progress)


def scan_pages(page_ids, country, max_ads, log, stop=lambda: False, progress=None):
    out = []
    with sync_playwright() as p:
        ctx = open_browser(p)
        try:
            for i, pid in enumerate(page_ids):
                if stop():
                    break
                if i:
                    gap = random.randint(*config.PAGE_GAP_S)
                    log(f"Nghỉ {gap} giây trước page tiếp theo (chế độ an toàn)")
                    for _ in range(gap):
                        if stop():
                            break
                        time.sleep(1)
                log(f"Đào page {pid}")
                base = len(out)
                out += collect(ctx, page_url(pid, country), max_ads, log, stop,
                               progress=(lambda n, b=base: progress(b + n)) if progress else None)
        finally:
            ctx.close()
    return out


# ---------------- Video viral: TikTok + Facebook Reels ----------------

TIKTOK = "https://www.tiktok.com"
CREATIVE_CENTER = "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
TREND_VIDEOS = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/video/pc/en"
TREND_TAGS = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"
FB = "https://www.facebook.com"


def tiktok_url(keyword):
    """'#dogmom' -> trang hashtag; còn lại -> tìm kiếm video."""
    kw = keyword.strip()
    if kw.startswith("#"):
        return f"{TIKTOK}/tag/{quote(kw[1:])}"
    return f"{TIKTOK}/search/video?" + urlencode({"q": kw})


def topads_url(country, period):
    return CREATIVE_CENTER + "?" + urlencode({"period": period, "region": country})


def trend_url(base, country, period):
    """Creative Center: video thịnh hành / hashtag xu hướng của 1 thị trường."""
    return base + "?" + urlencode({"period": period, "countryCode": country, "region": country})


def reels_url(keyword):
    return f"{FB}/search/videos/?" + urlencode({"q": keyword})


def _type_search(keyword):
    """Creative Center: gõ từ khoá vào ô tìm kiếm (nếu có) rồi Enter."""
    def prepare(page, log):
        if not keyword:
            return
        try:
            box = page.get_by_placeholder(re.compile("search", re.I)).first
            box.fill(keyword)
            box.press("Enter")
            log(f"Tìm '{keyword}' trong Top Ads")
        except Exception as e:
            log(f"Không gõ được từ khoá vào Top Ads ({e}); lấy Top Ads chung")
    return prepare


def scan_pinterest(geo, max_items, log, stop=lambda: False):
    """Pinterest Trends của 1 thị trường: đọc lỏng mọi JSON của trang có từ khoá + % tăng trưởng (thử nghiệm)."""
    from . import kwtrends
    return run_collect(
        config.PINTEREST_TRENDS.format(geo=geo), max_items, log, stop,
        match=lambda u: "trends" in u or "/resource/" in u, marker=("growth", "pct_"),
        parse_text=kwtrends.parse_pinterest_text, parse_page=kwtrends.parse_pinterest_html, key="term",
        noun="từ khoá", platform="pinterest")


def scan_social(platform, keyword, country, max_items, period, log, stop=lambda: False, progress=None):
    if platform == "tiktok":
        return run_collect(
            tiktok_url(keyword), max_items, log, stop, progress=progress,
            match=lambda u: any(k in u for k in ("/api/search/", "/api/challenge/item_list", "/api/post/item_list")),
            marker="playCount", parse_text=social.parse_tiktok_text, parse_page=social.parse_tiktok_html,
            key="vid", noun="video", platform="tiktok")
    if platform == "tiktok_ads":
        return run_collect(
            topads_url(country, period), max_items, log, stop, progress=progress,
            match=lambda u: "creative_radar_api" in u, marker="ad_title",
            parse_text=social.parse_topads_text, parse_page=lambda html: [], key="vid", noun="Top Ads",
            platform="tiktok", click_more="text=/View More|Xem thêm/i", prepare=_type_search(keyword))
    if platform == "tiktok_trend":
        return run_collect(
            trend_url(TREND_VIDEOS, country, period), max_items, log, stop, progress=progress,
            match=lambda u: "creative_radar_api" in u, marker=("item_url", "item_id"),
            parse_text=social.parse_trend_videos_text, parse_page=social.parse_trend_videos_html, key="vid",
            noun="video thịnh hành", platform="tiktok", click_more="text=/View More|Xem thêm/i")
    if platform == "tiktok_tags":
        return run_collect(
            trend_url(TREND_TAGS, country, period), max_items, log, stop, progress=progress,
            match=lambda u: "creative_radar_api" in u, marker="hashtag_name",
            parse_text=social.parse_hashtags_text, parse_page=social.parse_hashtags_html, key="name",
            noun="hashtag", platform="tiktok", click_more="text=/View More|Xem thêm/i")
    if platform == "fb_reels":
        return run_collect(
            reels_url(keyword), max_items, log, stop, progress=progress,
            marker=("play_count", "video_view_count"), parse_text=social.parse_reels_text,
            parse_page=social.parse_reels_html, key="vid", noun="video")
    raise ValueError(f"Nền tảng không hỗ trợ: {platform}")
