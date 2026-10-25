"""Gợi ý từ khoá từ xu hướng: Google Trends (tìm kiếm thịnh hành, đọc RSS công khai) và Pinterest Trends
(mở trang trends.pinterest.com bằng trình duyệt quét, đọc dữ liệu JSON của trang — thử nghiệm).

Kết quả lưu trong settings["kwtrends"] = {nguồn: {thị trường: {"ts": ..., "items": [...]}}}.
Mỗi mục: term (từ khoá), score (độ lớn để xếp), growth (% tăng, Pinterest), info (ghi chú ngắn), group (danh mục).
"""
import html
import json
import re
import time

SOURCES = {"pinterest": "Pinterest Trends", "google": "Google Trends"}

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)


def _tag(block, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
    if not m:
        return None
    v = m.group(1).strip()
    if v.startswith("<![CDATA["):
        v = v[9:-3]
    return html.unescape(v).strip()


def _traffic(s):
    """'20,000+' / '2K+' / '1M+' -> số."""
    if not s:
        return 0
    m = re.match(r"([0-9][0-9.,]*)\s*([KkMm]?)", s.strip())
    if not m:
        return 0
    n = float(m.group(1).replace(",", ""))
    return int(n * {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1))


def parse_google_rss(xml):
    out = []
    for block in _ITEM_RE.findall(xml or ""):
        term = _tag(block, "title")
        if not term:
            continue
        traffic = _tag(block, "ht:approx_traffic")
        news = _tag(block, "ht:news_item_title")
        out.append({"term": term.lower(), "score": _traffic(traffic), "growth": None,
                    "info": " · ".join(x for x in (f"{traffic} lượt tìm" if traffic else None, news) if x)[:200], "group": None})
    return out


_TERM_KEYS = ("term", "keyword", "query", "display_term", "search_term")
_GROUP_KEYS = ("category", "category_name", "interest", "vertical", "group")


def _growth(d):
    for k, v in d.items():
        kl = k.lower()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and ("growth" in kl or "pct" in kl or kl in ("wow", "mom", "yoy")):
            return k, float(v)
    return None, None


def _walk(x, group, out):
    if isinstance(x, dict):
        g = next((x[k] for k in _GROUP_KEYS if isinstance(x.get(k), str)), None) or group
        term = next((x[k] for k in _TERM_KEYS if isinstance(x.get(k), str) and x[k].strip()), None)
        gk, gv = _growth(x)
        if term and gk:
            # Pinterest trả % tăng dạng 0.52 hoặc 52 tuỳ chỗ: < 20 coi như tỉ lệ
            pct = round(gv * 100) if abs(gv) < 20 else round(gv)
            out.append({"term": term.strip().lower(), "score": pct, "growth": pct, "info": None, "group": g})
        for v in x.values():
            _walk(v, g, out)
    elif isinstance(x, list):
        for v in x:
            _walk(v, group, out)


def parse_pinterest_text(text):
    """Đọc lỏng phản hồi JSON của Pinterest Trends: mọi object có từ khoá + trường % tăng trưởng."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    out = []
    _walk(data, None, out)
    return out


def parse_pinterest_html(page):
    out = []
    for m in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', page or "", re.S):
        out += parse_pinterest_text(m.group(1))
    return out


def merge(items):
    """Bỏ trùng theo từ khoá, giữ điểm cao nhất, xếp giảm dần."""
    best = {}
    for it in items:
        t = it["term"]
        if t and (t not in best or (it["score"] or 0) > (best[t]["score"] or 0)):
            best[t] = it
    return sorted(best.values(), key=lambda it: (-(it["score"] or 0), it["term"]))


def save(db, source, market, items, now=None):
    data = db.get_setting("kwtrends", {})
    data.setdefault(source, {})[market] = {"ts": int(now or time.time()), "items": merge(items)[:200]}
    db.set_setting("kwtrends", data)
