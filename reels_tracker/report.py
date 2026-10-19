"""Per-scan view reports: the views of every tracked video, summed by Page/channel."""

import csv
import io
import threading
from datetime import datetime, timezone

PLATFORM_LABELS = {"facebook": "📘 Facebook", "youtube": "▶️ YouTube"}


class ScanReport:
    """Collects the views read during one scan of one platform (thread-safe)."""

    def __init__(self, platform, scanned_at=None):
        self.platform = platform
        self.scanned_at = scanned_at or datetime.now(timezone.utc)
        self.sources = {}  # source_id -> {"name", "error", "seen_before"}
        self.items = []
        self._lock = threading.Lock()

    def add_source(self, source_id, name, seen_before):
        with self._lock:
            self.sources[source_id] = {"name": name, "error": None, "seen_before": seen_before}

    def mark_error(self, source_id, error):
        with self._lock:
            self.sources[source_id]["error"] = str(error)

    def add_item(self, source_id, item_id, title, link, published, views, prev_views):
        with self._lock:
            self.items.append({
                "source_id": source_id,
                "item_id": item_id,
                "title": (title or "").strip(),
                "link": link,
                "published": published,
                "views": views,
                "prev_views": prev_views,
            })

    def summaries(self):
        """One dict per source: name, total views, change since last scan, videos."""
        result = []
        for source_id, source in self.sources.items():
            items = [i for i in self.items if i["source_id"] == source_id]
            for item in items:
                if item["prev_views"] is not None:
                    item["delta"] = item["views"] - item["prev_views"]
                else:
                    # A video first seen now: count it as growth only if the source was
                    # already tracked, otherwise the first report would be all "growth".
                    item["delta"] = item["views"] if source["seen_before"] else None
            deltas = [i["delta"] for i in items if i["delta"] is not None]
            result.append({
                "source_id": source_id,
                "name": source["name"],
                "error": source["error"],
                "total": sum(i["views"] for i in items),
                "delta": sum(deltas) if deltas else None,
                "new_videos": sum(1 for i in items if i["prev_views"] is None),
                "items": items,
            })
        result.sort(key=lambda s: s["total"], reverse=True)
        return result

    def snapshot_rows(self):
        names = {sid: s["name"] for sid, s in self.sources.items()}
        when = self.scanned_at.isoformat()
        return [
            (when, self.platform, i["source_id"], names.get(i["source_id"], ""), i["item_id"],
             i["title"], i["link"], i["published"].isoformat() if i["published"] else None,
             i["views"])
            for i in self.items
        ]


def _delta_text(delta):
    if delta is None:
        return ""
    return f" ({delta:+,})"


def _short(text, limit=50):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def format_report(reports, top_n=3, now_text=""):
    """Telegram text for the reports of one scan round."""
    lines = [f"📊 Báo cáo view{' — ' + now_text if now_text else ''}",
             "(số trong ngoặc = tăng so với lần quét trước)"]
    grand_total, grand_delta = 0, 0
    for report in reports:
        summaries = report.summaries()
        lines += ["", PLATFORM_LABELS.get(report.platform, report.platform)]
        if not summaries:
            lines.append("Chưa có Page/kênh nào.")
        for s in summaries:
            if s["error"]:
                lines.append(f"• {s['name']} — ⚠️ lỗi: {_short(s['error'], 80)}")
                continue
            new = f", {s['new_videos']} mới" if s["new_videos"] and s["delta"] is not None else ""
            lines.append(
                f"• {s['name']} — {s['total']:,} view{_delta_text(s['delta'])}"
                f" · {len(s['items'])} video{new}"
            )
            grand_total += s["total"]
            grand_delta += s["delta"] or 0
            # Fastest-growing videos first; on the first scan, the most viewed.
            ranked = sorted(
                s["items"],
                key=lambda i: (i["delta"] if i["delta"] is not None else -1, i["views"]),
                reverse=True,
            )
            for item in ranked[:top_n]:
                title = _short(item["title"]) or item["item_id"]
                lines.append(f"   ↑ {item['views']:,}{_delta_text(item['delta'])} — {title}")
                lines.append(f"     {item['link']}")
    lines += ["", f"Tổng cộng: {grand_total:,} view{_delta_text(grand_delta or None)}"]
    return "\n".join(lines)


CSV_HEADER = ["Thời gian quét", "Nền tảng", "Page/Kênh", "ID Page/Kênh", "ID video",
              "Tiêu đề/Caption", "Link", "Ngày đăng", "Views"]


def snapshots_csv(rows):
    """CSV bytes (UTF-8 with BOM so Excel shows Vietnamese correctly)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for scanned_at, platform, source_id, source_name, item_id, title, link, published, views \
            in rows:
        writer.writerow([scanned_at, platform, source_name, source_id, item_id,
                         title, link, published or "", views])
    return ("﻿" + buffer.getvalue()).encode("utf-8")
