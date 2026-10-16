"""Mọi ngưỡng chấm điểm nằm ở đây. Không có "điểm AI": mỗi nhãn là một luật đọc được."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Bản cài đặt (.exe) nằm trong Program Files, không ghi được -> lưu dữ liệu vào %LOCALAPPDATA%\SnakemediaPOD
FROZEN = getattr(sys, "frozen", False)
_default_data = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SnakemediaPOD") if FROZEN else ROOT / "data"
DATA_DIR = Path(os.environ.get("SNAKEPOD_DATA", _default_data))
DB_PATH = DATA_DIR / "snakepod.db"
THUMB_DIR = DATA_DIR / "thumbs"
BROWSER_PROFILE = DATA_DIR / "browser-profile"

HOST = "127.0.0.1"
PORT = int(os.environ.get("SNAKEPOD_PORT", "8765"))

# Quét
DEFAULT_COUNTRY = "US"
DEFAULT_MAX_ADS = 300          # số QC tối đa mỗi lượt quét từ khoá
DIG_MAX_PAGES = 6              # đào sâu: số page tối đa soi cho 1 video
DIG_MAX_ADS_PER_PAGE = 150
# Proxy cho trình duyệt quét Facebook: ghi 1 dòng vào file proxy.txt cạnh ChayTool.bat,
# dạng  http://user:pass@host:port  hoặc  socks5://host:port. Để trống = không dùng proxy.
PROXY_FILE = (DATA_DIR if FROZEN else ROOT) / "proxy.txt"
CHROMIUM_PATH = os.environ.get("SNAKEPOD_CHROMIUM") or None  # để trống = dùng Chromium do Playwright cài
HEADLESS = os.environ.get("SNAKEPOD_HEADLESS", "0") == "1"  # mặc định hiện trình duyệt, ít bị chặn hơn

# Chế độ an toàn: cuộn chậm như người thật (mili giây nghỉ giữa 2 lần cuộn, ngẫu nhiên trong khoảng)
SCROLL_PAUSE_MS = tuple(int(x) for x in os.environ.get("SNAKEPOD_SCROLL_MS", "2500,5500").split(","))
MAX_SCROLL_ROUNDS = 60          # tối đa số lần cuộn mỗi trang
PAGE_GAP_S = (20, 45)           # đào sâu nhiều page: nghỉ ngẫu nhiên giữa 2 page (giây)

AUTO_SCAN_HOUR = 1             # giờ tự quét mỗi đêm (giờ máy tính), sửa được trên giao diện

# Gom QC cùng 1 video: 2 ảnh thumbnail khác nhau <= N bit (dHash 64 bit) coi như cùng video
DHASH_MAX_DISTANCE = 6

# Luật chấm nhãn (đơn vị: ngày)
SCALE_MAX_DAYS = 7             # QC đang chạy < 7 ngày  -> "Scale" (mới lên)
WIN_MAX_DAYS = 14              # QC sống 7-14 ngày      -> "Win" (đã có người đổ tiền và giữ)
NEW_VIDEO_DAYS = 14            # video <= 14 ngày tuổi  -> còn mới
OLD_VIDEO_DAYS = 30            # video > 30 ngày tuổi   -> già, đi muộn
PAGE_OLDER_THAN_VIDEO = 14     # trang bán tạo trước video > 14 ngày -> tô đỏ
MIN_SHOPS_SAP_WIN = 2          # ít nhất 2 shop (domain) khác nhau đang chạy
MIN_SHOPS_WIN = 2              # ít nhất 2 shop giữ QC sống 7-14 ngày
MIN_SCALE_ADS = 5              # 1 shop bơm >= 5 QC mới trong 7 ngày -> "Video scale"
NEW_POST_DAYS = 3              # shop có QC bắt đầu trong 3 ngày -> "đang lên bài mới"

# QC Facebook "đang lan nhanh": nhiều QC / shop mới chép video trong 48 giờ qua
SPREAD_HOURS = 48
SPREAD_MIN_NEW_ADS = 5
SPREAD_MIN_NEW_SHOPS = 2

# Video viral (TikTok / Facebook Reels). vph = lượt xem mỗi giờ
VIRAL_EXPLODE_VPH = 20_000     # "Đang nổ": >= 20.000 lượt xem/giờ ...
VIRAL_EXPLODE_MAX_DAYS = 3     # ... và video <= 3 ngày tuổi
VIRAL_MIN_VIEWS = 1_000_000    # "Viral": >= 1 triệu lượt xem ...
VIRAL_MAX_DAYS = 14            # ... và video <= 14 ngày tuổi
VIRAL_RISING_VPH = 2_000       # "Đang lên": >= 2.000 lượt xem/giờ ...
VIRAL_RISING_MAX_DAYS = 7      # ... và video <= 7 ngày tuổi
