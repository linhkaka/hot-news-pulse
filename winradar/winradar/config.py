"""Mọi ngưỡng chấm điểm nằm ở đây. Không có "điểm AI": mỗi nhãn là một luật đọc được."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("WINRADAR_DATA", ROOT / "data"))
DB_PATH = DATA_DIR / "winradar.db"
THUMB_DIR = DATA_DIR / "thumbs"
BROWSER_PROFILE = DATA_DIR / "browser-profile"

HOST = "127.0.0.1"
PORT = int(os.environ.get("WINRADAR_PORT", "8765"))

# Quét
DEFAULT_COUNTRY = "US"
DEFAULT_MAX_ADS = 300          # số QC tối đa mỗi lượt quét từ khoá
DIG_MAX_PAGES = 6              # đào sâu: số page tối đa soi cho 1 video
DIG_MAX_ADS_PER_PAGE = 150
# Proxy cho trình duyệt quét Facebook: ghi 1 dòng vào file proxy.txt cạnh ChayTool.bat,
# dạng  http://user:pass@host:port  hoặc  socks5://host:port. Để trống = không dùng proxy.
PROXY_FILE = ROOT / "proxy.txt"
CHROMIUM_PATH = os.environ.get("WINRADAR_CHROMIUM") or None  # để trống = dùng Chromium do Playwright cài
HEADLESS = os.environ.get("WINRADAR_HEADLESS", "0") == "1"  # mặc định hiện trình duyệt, ít bị chặn hơn

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
