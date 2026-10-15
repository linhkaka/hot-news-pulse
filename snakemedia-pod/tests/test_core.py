import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from snakepod import analyze, config, fb_parser, landing
from snakepod.imagehash import distance

FIX = Path(__file__).parent / "fixtures"
DAY = 86400
NOW = 1_760_000_000


def test_parse_graphql_text():
    ads = {a["ad_id"]: a for a in fb_parser.parse_json_text((FIX / "graphql_response.txt").read_text())}
    assert set(ads) == {"111", "112", "113"}
    a = ads["111"]
    assert a["link_url"] == "https://www.bloomyard.com/products/blue-hosta"
    assert a["domain"] == "bloomyard.com"
    assert a["video_url"] == "https://video.fbcdn.net/v/hd.mp4"
    assert a["thumb_url"] == "https://scontent.fbcdn.net/thumb1.jpg"
    assert a["collation_count"] == 3 and a["is_active"] == 1
    assert ads["112"]["body"] is None          # biến DCO {{...}} bị bỏ
    assert ads["112"]["thumb_url"] == "https://scontent.fbcdn.net/img.jpg"
    c = ads["113"]                              # QC dạng carousel
    assert c["title"] == "Card title" and c["domain"] == "shop.example" and c["video_url"].endswith("c.mp4")


def test_parse_html_embedded_json():
    blob = json.dumps({"x": [{"ad_archive_id": "7", "page_id": "1", "snapshot": {"body": {"text": "hi"}}}]})
    html = f'<html><script type="application/json" data-sjs>{blob}</script><script type="application/json">{{}}</script></html>'
    ads = fb_parser.parse_html(html)
    assert [a["ad_id"] for a in ads] == ["7"] and ads[0]["body"] == "hi"


def test_distance():
    assert distance("ffff000000000000", "ffff000000000001") == 1


def _ad(ad_id, domain, age, active=True, dhash="aaaaaaaaaaaaaaaa", page=None, link=None):
    return {"ad_id": ad_id, "domain": domain, "page_id": page or domain, "start_ts": NOW - age * DAY,
            "is_active": 1 if active else 0, "dhash": dhash, "collation_count": 1,
            "link_url": link or f"https://{domain}/products/p", "body": "x"}


def test_cluster_by_near_duplicate_hash():
    ads = [_ad("1", "a.com", 3, dhash="aaaaaaaaaaaaaaaa"),
           _ad("2", "b.com", 3, dhash="aaaaaaaaaaaaaaab"),   # cách 1 bit -> cùng video
           _ad("3", "c.com", 3, dhash="5555555555555555")]   # khác hẳn
    groups = sorted(sorted(a["ad_id"] for a in g) for g in analyze.cluster(ads).values())
    assert groups == [["1", "2"], ["3"]]


def _label(ads, landings=None):
    return analyze.summarize("x", ads, landings or {}, now=NOW)


def test_video_age_uses_earliest_ad_including_inactive():
    v = _label([_ad("1", "a.com", 5), _ad("2", "b.com", 40, active=False)])
    assert v["video_age_days"] == 40 and v["label"] == "cu"


def test_sap_win():
    v = _label([_ad("1", "a.com", 5), _ad("2", "b.com", 2)])
    assert v["label"] == "sap_win" and v["shops_active"] == 2


def test_win_needs_two_shops_keeping_ads_7_to_14_days():
    v = _label([_ad("1", "a.com", 10), _ad("2", "b.com", 8), _ad("3", "c.com", 1)])
    assert v["label"] == "win" and v["shops_win"] == 2 and v["buckets"] == {"scale": 1, "win": 2, "old": 0}


def test_old_landing_page_is_flagged():
    link = "https://a.com/products/p"
    v = _label([_ad("1", "a.com", 5, link=link), _ad("2", "b.com", 2)],
               {link: {"created_ts": NOW - 30 * DAY, "price": "9.99"}})
    assert v["page_old"] and v["label"] == "trang_cu" and v["price"] == "9.99"


def test_single_shop_scaling():
    v = _label([_ad(str(i), "a.com", 2) for i in range(config.MIN_SCALE_ADS)])
    assert v["label"] == "scale"


def test_shopify_landing_check():
    def handler(req):
        if req.url.path.endswith(".json"):
            return httpx.Response(200, json={"product": {"title": "Blue Hosta", "created_at": "2026-10-01T10:00:00-04:00",
                                                          "published_at": None, "variants": [{"price": "14.99"}]}})
        return httpx.Response(200, text='<html><script src="https://cdn.shopify.com/x.js"></script></html>')
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        info = landing.check("https://bloomyard.com/products/blue-hosta", c)
    assert info["platform"] == "shopify" and info["price"] == "14.99" and info["title"] == "Blue Hosta"
    assert info["created_ts"] == int(datetime(2026, 10, 1, 14, tzinfo=timezone.utc).timestamp()) and info["error"] is None


def test_landing_check_records_errors():
    def handler(req):
        raise httpx.ConnectError("boom")
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        info = landing.check("https://down.example/products/x", c)
    assert info["error"] and info["created_ts"] is None


def test_read_proxy(tmp_path, monkeypatch):
    from snakepod import scraper
    monkeypatch.delenv("SNAKEPOD_PROXY", raising=False)
    f = tmp_path / "proxy.txt"
    monkeypatch.setattr(config, "PROXY_FILE", f)
    assert scraper.read_proxy() is None
    f.write_text("# chú thích\n# http://x:1\n", encoding="utf-8")
    assert scraper.read_proxy() is None
    f.write_text("# chú thích\nhttp://us%40er:p%3Ass@1.2.3.4:8080\n", encoding="utf-8")
    assert scraper.read_proxy() == {"server": "http://1.2.3.4:8080", "username": "us@er", "password": "p:ss"}
    monkeypatch.setenv("SNAKEPOD_PROXY", "5.6.7.8:3128")
    assert scraper.read_proxy() == {"server": "http://5.6.7.8:3128"}
