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

HTTP_WORKERS = 8                # số luồng tải ảnh / đọc trang bán cùng lúc (không đụng Facebook/TikTok)

# Gom QC cùng 1 video: 2 ảnh thumbnail khác nhau <= N bit (dHash 64 bit) coi như cùng video
DHASH_MAX_DISTANCE = 6
# Ảnh hơi khác hơn (video bị cắt, thêm chữ) vẫn gom nếu QC có cùng nội dung chữ hoặc cùng sản phẩm trên trang bán
DHASH_LOOSE_DISTANCE = 12

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

# Video Tiềm Năng: vừa nhú, shop bắt đầu nhảy vào nhưng chưa chín (chưa đủ điều kiện Sắp WIN / Win)
POTENTIAL_MAX_DAYS = 10        # video <= 10 ngày tuổi ...
POTENTIAL_MIN_NEW_ADS = 2      # ... và >= 2 QC mới trong 48 giờ
POTENTIAL_MIN_PAGES = 2        # ... hoặc >= 2 page đang chạy

# SP bò sữa: chạy đều nhiều tuần, không bùng lên rồi tắt (hợp Google Shopping / SEO / sàn / free traffic)
COW_MIN_DAYS = 30              # video >= 30 ngày tuổi
COW_MIN_RUN_DAYS = 21          # có QC đang chạy liên tục >= 21 ngày
COW_MIN_OLD_ADS = 5            # >= 5 QC đang chạy đã sống > 14 ngày
COW_MIN_SHOPS = 3              # >= 3 shop đang chạy

DIG_FRESH_DAYS = 7             # video đã đào trong 7 ngày -> không cần đào lại
STORE_FRESH_DAYS = 7           # shop đã soi trong 7 ngày -> "Đã soi"
AUTO_SWEEP_STORES = 20         # mỗi đêm soi thêm 20 shop đang chạy video hot (sửa được trên giao diện)
HISTORY_DAYS = 14              # lịch sử theo dõi mỗi video: giữ 14 ngày gần nhất trên giao diện

# Tìm nguồn hàng: {q} = tên sản phẩm, {image} = link ảnh. Thêm/bớt tuỳ ý.
SOURCING = [
    ("Google Lens (theo ảnh)", "https://lens.google.com/uploadbyurl?url={image}"),
    ("AliExpress", "https://www.aliexpress.com/wholesale?SearchText={q}"),
    ("Amazon", "https://www.amazon.com/s?k={q}"),
    ("Temu", "https://www.temu.com/search_result.html?search_key={q}"),
    ("CJdropshipping", "https://www.google.com/search?q=site%3Acjdropshipping.com+{q}"),
]

# Tải ảnh / video QC: thư mục lưu khi tải hàng loạt (mặc định Downloads\SnakemediaPOD)
MEDIA_DIR = Path(os.environ.get("SNAKEPOD_MEDIA", Path.home() / "Downloads" / "SnakemediaPOD"))
MEDIA_BATCH_MAX = 200          # tối đa số video mỗi lần tải hàng loạt

# Thị trường cho video viral. Nguồn chọn được thị trường: TikTok Top Ads, TikTok xu hướng (video / hashtag)
# của Creative Center. TikTok tìm kiếm thường và Facebook Reels ra kết quả theo tài khoản + IP của bạn.
MARKETS = {"US": "Mỹ", "GB": "Anh", "CA": "Canada", "AU": "Úc", "DE": "Đức", "FR": "Pháp", "IT": "Ý", "ES": "Tây Ban Nha",
           "NL": "Hà Lan", "JP": "Nhật", "BR": "Brazil", "MX": "Mexico", "VN": "Việt Nam"}

# Kết nối Shopify (nút Clone): đưa sản phẩm của trang bán vào store của bạn dưới dạng NHÁP (Draft)
SHOPIFY_API_VERSION = "2025-10"
SHOPIFY_SCOPES = "write_products,read_products"
SHOPIFY_BASE = os.environ.get("SNAKEPOD_SHOPIFY_BASE") or None   # chỉ dùng khi kiểm thử (máy chủ Shopify giả)
CLONE_MAX_IMAGES = 20
CLONE_MAX_VARIANTS = 100

# Gợi ý từ khoá từ xu hướng: Google Trends (RSS tìm kiếm thịnh hành) + Pinterest Trends (mở trang bằng trình duyệt)
GOOGLE_TRENDS_RSS = os.environ.get("SNAKEPOD_GTRENDS") or "https://trends.google.com/trending/rss?geo={geo}"
PINTEREST_TRENDS = os.environ.get("SNAKEPOD_PTRENDS") or "https://trends.pinterest.com/?country={geo}"
