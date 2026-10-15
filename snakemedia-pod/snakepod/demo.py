"""Tạo dữ liệu GIẢ để xem thử giao diện mà không cần quét Facebook.

Chạy:  set SNAKEPOD_DATA=data_demo  &&  python -m snakepod.demo  &&  python -m snakepod
(ChayDemo.bat làm sẵn việc này, dữ liệu demo nằm riêng trong data_demo/.)
"""
import io
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
     [("advent-cozy.com", 6, [4, 3, 3, 2, 1, 1])], 0),
    ("Veteran Truck Flag 🇺🇸 Proud army veteran", "34.99", 3, None,
     [("moto-loud.com", 2, [3, 2])], 0),
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


def main():
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
                             "date_source": "api" if lage else None})
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
    db.replace_videos(analyze.build_videos(db.all_ads(), db.landings_by_url()))
    db.add_watch_keyword("dog mom shirt", "US")
    db.add_watch_keyword("personalized ornament", "US")
    db.add_follow("shop", "bloomyard.com", "bloomyard.com")
    db.add_follow("page", "100", "Bloomyard 1")
    print(f"Đã tạo {len(ads)} QC demo trong {config.DATA_DIR}")


if __name__ == "__main__":
    main()
