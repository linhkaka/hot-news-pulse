"""Tạo dữ liệu GIẢ để xem thử giao diện mà không cần quét Facebook.

Chạy:  set SNAKEPOD_DATA=data_demo  &&  python -m snakepod.demo  &&  python -m snakepod
(ChayDemo.bat làm sẵn việc này, dữ liệu demo nằm riêng trong data_demo/.)
"""
import io
import shutil
import json
import random
import time

from PIL import Image, ImageDraw

from . import analyze, config, db
from .imagehash import dhash

DAY = 86400
PRODUCTS = [
    # (nội dung, giá, ngày tuổi video, ngày tuổi trang bán, [(shop, số QC, [tuổi QC đang chạy])], số QC đã tắt)
    ("Personalized Dog Mom Shirt 🐶 Custom name tee for every dog lover", "14.99", 6, 6,
     [("bloomyard.com", 3, [5, 4, 2]), ("gardenjoy.shop", 2, [6, 1])], 2),
    ("Funny Nurse Coffee Mug ☕ The gift every night-shift nurse needs", "26.00", 12, 11,
     [("skyflyer.co", 4, [11, 9, 8, 3]), ("kidzone-us.com", 3, [10, 7, 2]), ("toyrush.store", 1, [4])], 5),
    ("Custom Family Christmas Ornament 🎄 Add your names", "27.99", 14, 15,
     [("autoneat.com", 3, [13, 8, 1]), ("drivepro.shop", 2, [9, 3])], 4),
    ("Halloween Witch Doormat 🧹 Spooky season is here", "22.99", 9, 40,
     [("xmasglow.com", 4, [8, 6, 3, 1]), ("festivehome.co", 2, [5, 2])], 1),
    ("Fishing Grandpa Hoodie 🎣 Reel cool papa", "19.99", 48, 50,
     [("edcgear.com", 3, [40, 20, 3]), ("pocketpro.shop", 2, [30, 15])], 12),
    ("In Loving Memory Canvas 🕊 Personalized memorial wall art", "29.99", 4, 4,
     [("advent-cozy.com", 6, [4, 3, 2, 1, 1, 0]), ("memorialgift.co", 2, [1, 0])], 0),
    ("Veteran Truck Flag 🇺🇸 Proud army veteran", "34.99", 3, None,
     [("moto-loud.com", 2, [3, 2])], 0),
    ("Grandma's Garden Flag 🌻 Personalized with grandkids names", "24.99", 60, 58,
     [("flagcraft.co", 3, [55, 40, 25, 18, 3]), ("yardjoy.shop", 2, [35, 22, 10]), ("porchpride.com", 2, [28, 16])], 6),
]


def _img(seed):
    rnd = random.Random(seed)
    im = Image.new("RGB", (320, 320), tuple(rnd.randint(40, 220) for _ in range(3)))
    d = ImageDraw.Draw(im)
    for _ in range(6):
        x, y = rnd.randint(0, 260), rnd.randint(0, 260)
        d.ellipse([x, y, x + rnd.randint(40, 120), y + rnd.randint(40, 120)],
                  fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


SOCIAL = [
    # (nền tảng, id, caption, tác giả, giờ tuổi, [lượt xem theo 2 lần quét cách 6 giờ], thích, bình luận, chia sẻ, extra)
    ("tiktok", "7301", "POV: you ordered the personalized dog mom hoodie 🐶 #dogmom #customgift", "pawsandprints",
     30, [600_000, 1_100_000], 140_000, 2_100, 9_800, None),
    ("tiktok", "7302", "Nurse tumbler that survives a 12h shift ☕ #nurse #nurselife", "nightshiftnina",
     120, [2_300_000, 2_380_000], 310_000, 4_200, 21_000, None),
    ("tiktok", "7303", "Custom family christmas ornament unboxing 🎄 add your names", "cozyhomefinds",
     70, [180_000, 260_000], 22_000, 340, 1_200, None),
    ("tiktok", "7304", "Fishing grandpa shirt restock 🎣", "reelcoolpapa", 600, [90_000, 90_400], 4_000, 50, 90, None),
    ("tiktok_ads", "ad9001", "Personalized pet portrait canvas - turn your dog into art", "PawCanvas", None, [None],
     54_000, 800, 1_900, {"brand_name": "PawCanvas", "ctr": "Top 5%", "cost": 3, "industry_key": "Home Decor"}),
    ("tiktok_ads", "ad9002", "Teacher appreciation mug they will actually use", "MugMuse", None, [None],
     12_000, 150, 400, {"brand_name": "MugMuse", "ctr": "Top 20%", "cost": 2, "industry_key": "Gifts"}),
    ("fb_reels", "r501", "Memorial canvas made her cry 😭 personalized in loving memory", "Forever Prints",
     40, [350_000, 520_000], 18_000, 2_400, 6_100, None),
]


TRENDS = {  # thị trường -> [(hashtag, lượt xem, số bài)]
    "US": [("dogmom", 98_000_000, 41_000), ("nursesoftiktok", 76_000_000, 28_000), ("halloweendecor", 64_000_000, 19_500),
           ("customgifts", 31_000_000, 9_800), ("grandmagifts", 12_000_000, 3_100)],
    "GB": [("dogmum", 21_000_000, 7_300), ("christmasjumper", 18_000_000, 6_200), ("customgifts", 9_000_000, 2_400)],
}


# Gợi ý từ khoá mẫu: (từ khoá, danh mục, % tăng) của Pinterest Trends; (từ khoá, lượt tìm) của Google Trends
PIN_TRENDS = [("fireplace decor", "Home decor", 264), ("witch costume", "Costumes & accessories", 96),
              ("christmas porch decor", "Seasonal & holiday decorations", 77), ("dog mom shirt", "Pet supplies", 76),
              ("cowboy boots", "Shoes", 56), ("cozy slippers", "Shoes", 54), ("personalized ornament", "Seasonal & holiday decorations", 48)]
GOOGLE_TRENDS = [("halloween costumes", 500000), ("ugly christmas sweater", 50000), ("heated blanket", 20000)]


def _demo_trends(now):
    db.set_setting("kwtrends", {
        "pinterest": {"US": {"ts": now - 3600, "items": [{"term": t, "score": g, "growth": g, "info": None, "group": c}
                                                         for t, c, g in PIN_TRENDS]}},
        "google": {"US": {"ts": now - 7200, "items": [{"term": t, "score": n, "growth": None, "info": f"{n // 1000}K+ lượt tìm",
                                                       "group": None} for t, n in GOOGLE_TRENDS]}}})
    for market, tags in TRENDS.items():
        old = [{"name": n, "rank": i + 2 if i % 2 else i + 1} for i, (n, _, _) in enumerate(tags)]
        db.upsert_trends(market, old, now=now - DAY)
        db.upsert_trends(market, [{"name": n, "rank": i + 1, "views": v, "posts": p,
                                   "trend": [[now - (6 - d) * DAY, round(0.3 + 0.1 * d + 0.05 * i, 2)] for d in range(7)]}
                                  for i, (n, v, p) in enumerate(tags)], now=now)
    db.upsert_social([{"vid": "tiktok_trend:7401", "platform": "tiktok_trend", "item_id": "7401",
                       "url": "https://www.tiktok.com/", "author": None, "caption": "Dog mum hoodie reveal 🐾 #dogmum",
                       "cover_url": None, "video_url": None, "views": None, "likes": None, "comments": None, "shares": None,
                       "saves": None, "created_ts": None, "duration": 18, "extra": None}], "demo", now=now, market="GB")
    (config.THUMB_DIR / "s_demo_7401.jpg").write_bytes(_img(150))
    db.set_social_cover("tiktok_trend:7401", "s_demo_7401.jpg")


def _demo_social(now):
    for i, (plat, item_id, cap, author, age_h, views, likes, comments, shares, extra) in enumerate(SOCIAL):
        img = _img(100 + i)
        name = f"s_demo_{item_id}.jpg"
        (config.THUMB_DIR / name).write_bytes(img)
        base = {"vid": f"{plat}:{item_id}", "platform": plat, "item_id": item_id,
                "url": "https://www.tiktok.com/" if plat != "fb_reels" else "https://www.facebook.com/reel/",
                "author": author, "caption": cap, "cover_url": None, "video_url": None, "saves": None,
                "created_ts": now - age_h * 3600 if age_h else None, "duration": 20,
                "extra": json.dumps(extra, ensure_ascii=False) if extra else None,
                "likes": likes, "comments": comments, "shares": shares}
        for k, v in enumerate(views):
            db.upsert_social([{**base, "views": v}], "demo", now=now - (len(views) - 1 - k) * 6 * 3600)
        db.set_social_cover(base["vid"], name)
    db.add_social_watch("tiktok", "dog mom shirt", "")
    db.add_social_watch("tiktok_ads", "", "US")
    db.add_social_watch("tiktok_tags", "", "US")
    _demo_trends(now)


def _demo_history(videos, now):
    """Lịch sử theo dõi 3 ngày: số liệu hôm trước nhỏ hơn hôm nay một chút."""
    from datetime import datetime
    for back, k in ((2, 0.6), (1, 0.8), (0, 1.0)):
        day = datetime.fromtimestamp(now - back * DAY).strftime("%Y-%m-%d")
        db.record_history([{**v, "pages_active": int(v["pages_active"] * k), "shops_active": int(v["shops_active"] * k),
                            "shops_win": int(v["shops_win"] * k), "ads_active": int(v["ads_active"] * k),
                            "buckets": {**v["buckets"], "scale": int(v["buckets"]["scale"] * k)}} for v in videos], day)


def main():
    # Dữ liệu demo luôn tạo mới để tuổi QC/video đúng như mô tả. Chốt an toàn: chỉ xoá khi CSDL
    # chỉ chứa dữ liệu demo; gặp dữ liệu thật thì dừng, không đụng vào.
    if config.DB_PATH.exists():
        db.init()
        with db.connect() as conn:
            real = conn.execute("SELECT COUNT(*) FROM ads WHERE ad_id NOT LIKE 'demo%'").fetchone()[0]
            real += conn.execute("SELECT COUNT(*) FROM social_videos WHERE keyword IS NOT 'demo'").fetchone()[0]
        if real:
            raise SystemExit(f"{config.DATA_DIR} có dữ liệu thật, không tạo demo ở đây. "
                             "Đặt SNAKEPOD_DATA sang thư mục khác (ChayDemo.bat làm sẵn việc này).")
        config.DB_PATH.unlink()
        shutil.rmtree(config.THUMB_DIR, ignore_errors=True)
    db.init()
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    ads, n = [], 0
    for pi, (text, price, vage, lage, shops, gone) in enumerate(PRODUCTS):
        img = _img(pi)
        h = dhash(img)
        for si, (shop, pages, runs) in enumerate(shops):
            link = f"https://{shop}/products/demo-{pi}"
            db.save_landing({"url": link, "final_url": link, "domain": shop, "platform": "shopify",
                             "created_ts": now - lage * DAY if lage else None, "published_ts": None,
                             "title": text, "price": price, "checked_ts": now, "error": None,
                             "date_source": "api" if lage else None,
                             "compare_price": f"{float(price) * 2:.2f}" if pi % 2 == 1 else None})
            all_runs = [(r, True) for r in runs] + [(vage - k % 3, False) for k in range(gone if si == 0 else 0)]
            all_runs[0] = (max(all_runs[0][0], vage) if si == 0 else all_runs[0][0], True)
            for k, (age, active) in enumerate(all_runs):
                n += 1
                ad_id = f"demo{n}"
                (config.THUMB_DIR / f"{ad_id}.jpg").write_bytes(img)
                ads.append({"ad_id": ad_id, "collation_id": None, "collation_count": 1,
                            "page_id": f"{pi}{si}{k % pages}", "page_name": f"{shop.split('.')[0].title()} {k % pages + 1}",
                            "start_ts": now - age * DAY, "end_ts": None if active else now - DAY,
                            "is_active": 1 if active else 0, "title": None, "body": text, "link_url": link,
                            "domain": shop, "thumb_url": None, "thumb_path": f"{ad_id}.jpg", "video_url": None,
                            "dhash": h, "keyword": "demo", "first_seen": now, "last_seen": now})
    db.upsert_ads(ads, "demo")
    for a in ads:
        db.set_thumb(a["ad_id"], a["thumb_path"], a["dhash"])
    videos = analyze.build_videos(db.all_ads(), db.landings_by_url())
    db.replace_videos(videos)
    _demo_history(videos, now)
    db.set_mark(videos[0]["cid"], "test", True)
    _demo_social(now)
    db.add_watch_keyword("dog mom shirt", "US")
    db.add_watch_keyword("personalized ornament", "US")
    db.add_follow("shop", "bloomyard.com", "bloomyard.com")
    db.add_follow("page", "100", "Bloomyard 1")
    db.set_setting("schema", 2)               # dữ liệu mẫu đã chấm theo bản mới
    print(f"Đã tạo {len(ads)} QC demo trong {config.DATA_DIR}")


if __name__ == "__main__":
    main()
