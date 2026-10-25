"""Bộ chấm điểm của tiện ích (JavaScript) phải cho KẾT QUẢ GIỐNG HỆT bản app (Python) trên cùng dữ liệu."""
import json
import random
import uuid
from pathlib import Path

from snakepod import analyze, fb_parser, landing, pod, social

NOW = 1_760_000_000
DAY = 86400
FIX = Path(__file__).resolve().parent.parent.parent / "snakemedia-pod" / "tests" / "fixtures"


def _close(a, b, path=""):
    """So 2 kết quả; số thực được lệch rất nhỏ."""
    if isinstance(a, float) or isinstance(b, float):
        assert a is not None and b is not None and abs(a - b) < 1e-6, f"{path}: {a} != {b}"
    elif isinstance(a, dict):
        assert set(a) == set(b), f"{path}: khoá khác {set(a) ^ set(b)}"
        for k in a:
            _close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{path}: {a} != {b}"
        for i, (x, y) in enumerate(zip(a, b)):
            _close(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def _random_ads(seed, n=400):
    rnd = random.Random(seed)
    bases = [rnd.getrandbits(64) for _ in range(30)]
    launch = [rnd.choice([3, 10, 13, 20, 40]) for _ in bases]   # mỗi video ra mắt cách đây 3-40 ngày
    bodies = ["Personalized dog mom shirt custom name for you", "Funny nurse coffee mug gift idea today",
              "Custom family christmas ornament add your names now", "Halloween witch doormat spooky", "hi",
              None, "Fishing grandpa hoodie reel cool papa 🎣 limited", "In loving memory canvas memorial wall art"]
    shops = [f"shop{i}.com" for i in range(6)]
    ads = []
    for i in range(n):
        b = rnd.randrange(len(bases))
        h = bases[b]
        for _ in range(rnd.choice([0, 0, 0, 1, 2, 5, 9])):
            h ^= 1 << rnd.randrange(64)
        shop = rnd.choice(shops)
        ads.append({
            "ad_id": f"{rnd.randrange(10**6)}{i}", "collation_id": rnd.choice([None, None, None, f"c{rnd.randrange(30)}"]),
            "collation_count": rnd.choice([1, 1, 1, 2, 5]), "page_id": f"p{rnd.randrange(40)}", "page_name": "Page",
            "start_ts": NOW - rnd.randrange(0, launch[b] * DAY) if rnd.random() > 0.03 else None,
            "end_ts": None, "is_active": rnd.choice([1, 1, 1, 0]), "title": rnd.choice([None, "Shop now"]),
            "body": bodies[b % len(bodies)] if rnd.random() > 0.2 else rnd.choice(bodies), "domain": shop if rnd.random() > 0.05 else None,
            "link_url": f"https://{shop}/products/{rnd.choice(['personalized-dog-mom-shirt', 'nurse-mug-gift-1', 'p', 'custom-family-ornament-2'])}",
            "thumb_url": None, "thumb_path": rnd.choice([None, f"{i}.jpg"]), "video_url": rnd.choice([None, "v.mp4"]),
            "dhash": f"{h:016x}" if rnd.random() > 0.1 else None, "keyword": rnd.choice([None, "dog", "nurse mug"]),
            "first_seen": NOW, "last_seen": NOW - rnd.randrange(1000)})
    landings = {}
    for shop in shops:
        for prod in ["personalized-dog-mom-shirt", "nurse-mug-gift-1", "p", "custom-family-ornament-2"]:
            if rnd.random() < 0.6:
                landings[f"https://{shop}/products/{prod}"] = {
                    "created_ts": NOW - rnd.randrange(0, 30 * DAY) if rnd.random() > 0.2 else None,
                    "date_source": rnd.choice(["api", "uuid", "anh"]), "title": rnd.choice([None, "Gift Tee", "Wine glass"]),
                    "price": "19.99", "compare_price": rnd.choice([None, "39.99"]), "platform": rnd.choice([None, "shopify", "printify", "shoplazza"]),
                    "pod_markers": rnd.choice([None, "customily", "printify,teeinblue"])}
    return ads, landings


def test_build_videos_matches_python(ext):
    labels, flags = set(), set()
    for seed in range(4):
        ads, landings = _random_ads(seed)
        py = analyze.build_videos([dict(a) for a in ads], landings, now=NOW)
        js = ext.js("([a, l, t]) => SP.analyze.buildVideos(a, l, t)", [ads, landings, NOW])
        assert len(py) == len(js) > 20
        _close(sorted(py, key=lambda v: v["cid"]), sorted(js, key=lambda v: v["cid"]), f"seed{seed}")
        labels |= {v["label"] for v in py}
        flags |= {k for v in py for k in ("potential", "cash_cow") if v[k]} | ({"compare"} if any(v["compare_price"] for v in py) else set())
    assert labels == {"sap_win", "win", "scale", "theo_doi", "trang_cu", "cu"}     # dữ liệu thử đủ mọi nhãn
    assert flags == {"potential", "cash_cow", "compare"}                            # ... và đủ tab Tiềm năng / Bò sữa


def test_cluster_matches_python(ext):
    ads, _ = _random_ads(9, 600)
    py = sorted(sorted(a["ad_id"] for a in g) for g in analyze.cluster(ads).values())
    js = sorted(sorted(g) for g in ext.js("a => [...SP.analyze.cluster(a).values()].map(g => g.map(x => x.ad_id))", ads))
    assert py == js


def test_pod_classify_matches_python(ext):
    texts = ["Personalized Dog Mom T-Shirt with name", "Funny nurse coffee mug", "custom_family christmas ornaments",
             "Halloween witch doormat & garden flag", "RN life tumbler for ICU nurses", "God bless america veteran hat",
             "", "Wine glass for mothers day, engraved", "Golden retriever blanket - personalised", "a cat"]
    py = [list(pod.classify(t)) for t in texts]
    js = ext.js("ts => ts.map(t => SP.pod.classify(t))", texts)
    assert py == js
    html = "<script src='https://cdn.customily.com/x.js'></script> Printify teeinblue"
    assert pod.detect_pod_markers(html) == ext.js("h => SP.pod.detectPodMarkers(h)", html)


def test_landing_dates_match_python(ext):
    u1 = str(uuid.uuid1())
    samples = [
        '{"created_at":"2025-03-04T05:06:07-04:00","title":"x"}',
        '{"createdAt": "2024-11-02 10:00:00"}',
        '{"published_at":"2025-01-01T00:00:00.123456Z"}',
        '{"create_time": 1712345678901}',
        f'{{"product_id":"{u1}"}}',
        '<img src="https://cdn.shopify.com/s/files/1/a.jpg?v=1712345678">',
        '<img src="/wp-content/uploads/2023/07/a.jpg">',
        '{"created_at":"1999-01-01T00:00:00Z"}', "nothing here",
    ]
    py = [list(landing.dates_from_html(s)) for s in samples]
    js = ext.js("ss => ss.map(s => SP.landing.datesFromHtml(s))", samples)
    assert py == js
    assert landing.uuid1_ts(u1) == ext.js("u => SP.landing.uuid1Ts(u)", u1)
    for h in ['<script src="https://cdn.shopify.com/x">', "shoplazza", "woocommerce", "x gearlaunch", "plain"]:
        assert landing.detect_platform(h) == ext.js("h => SP.landing.detectPlatform(h)", h)


def test_fb_parser_matches_python(ext):
    text = (FIX / "graphql_response.txt").read_text()
    assert fb_parser.parse_json_text(text) == ext.js("t => SP.fbparser.parseJsonText(t)", text)
    blob = json.dumps({"x": [{"ad_archive_id": "7", "page_id": "1", "snapshot": {"body": {"text": "hi"},
                                                                                 "link_url": "https://l.facebook.com/l.php?u=https%3A%2F%2Fwww.Shop.com%2Fproducts%2Fa%2F%3Futm%3D1"}}]})
    html = f'<html><script type="application/json" data-sjs>{blob}</script></html>'
    assert fb_parser.parse_html(html) == ext.js("h => SP.fbparser.parseHtml(h)", html)
    # ID quá dài cho số JavaScript vẫn giữ đúng từng chữ số
    big = '{"ad_archive_id": 1234567890123456789, "page_id": 9876543210987654321, "snapshot": {}}'
    assert ext.js("t => SP.fbparser.parseJsonText(t)[0].ad_id", big) == "1234567890123456789"


def test_social_parsers_and_labels_match_python(ext):
    def tt(i, views, age_h):
        return {"id": i, "desc": "Nurse mug #nurse", "createTime": NOW - age_h * 3600, "author": {"uniqueId": "u"},
                "stats": {"playCount": views, "diggCount": "1.2K", "commentCount": 0, "shareCount": 7},
                "statsV2": {"playCount": str(views + 5)}, "video": {"cover": "c.jpg", "playAddr": "p.mp4"}}
    texts = [
        json.dumps({"item_list": [tt("1", 5000, 10), tt("2", 2_000_000, 100)]}),
        json.dumps({"data": {"materials": [{"id": 77, "ad_title": "Pet canvas", "brand_name": "Paw", "like": 5, "ctr": 0.1,
                                            "video_info": {"cover": "c", "video_url": {"720p": "v"}, "duration": 21.5}}]}}),
        json.dumps({"data": {"node": {"id": "r1", "play_count": 350000, "creation_time": NOW - 40 * 3600,
                                      "owner": {"name": "F"}, "message": {"text": "Memorial canvas"},
                                      "feedback": {"reaction_count": {"count": 1800}, "share_count": {"count": 61}}}}}),
    ]
    assert social.parse_tiktok_text(texts[0]) == ext.js("t => SP.social.parseTiktokText(t)", texts[0])
    py_ads, js_ads = social.parse_topads_text(texts[1]), ext.js("t => SP.social.parseTopadsText(t)", texts[1])
    assert [json.loads(x.pop("extra")) for x in py_ads] == [json.loads(x.pop("extra")) for x in js_ads] and py_ads == js_ads
    assert social.parse_reels_text(texts[2]) == ext.js("t => SP.social.parseReelsText(t)", texts[2])

    rnd = random.Random(3)
    for i in range(60):
        plat = rnd.choice(["tiktok", "tiktok", "fb_reels", "tiktok_ads"])
        row = {"vid": f"{plat}:{i}", "platform": plat, "views": rnd.choice([None, rnd.randrange(10**7)]),
               "likes": rnd.choice([None, rnd.randrange(10**5)]), "comments": rnd.randrange(1000), "shares": rnd.randrange(5000),
               "created_ts": rnd.choice([None, NOW - rnd.randrange(1, 30 * DAY)]), "caption": rnd.choice(["Nurse mug", "dog mom tee", None]),
               "extra": rnd.choice([None, '{"ctr": "Top 5%", "cost": 3}']), "keyword": None, "first_seen": NOW, "last_seen": NOW}
        snaps = sorted((NOW - rnd.randrange(0, 3 * DAY), rnd.choice([None, rnd.randrange(10**7)]), 1, 2, 3) for _ in range(rnd.randrange(4)))
        py = social.summarize(row, snaps, now=NOW)
        js = ext.js("([r, s, t]) => SP.social.summarize(r, s, t)", [row, [list(s) for s in snaps], NOW])
        _close(py, js, f"row{i}")
