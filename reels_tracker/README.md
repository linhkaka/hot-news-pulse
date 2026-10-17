# Reels Tracker → Telegram

Tool chạy 24/7, theo dõi Reels của các Facebook Page. Reel nào **vượt 5.000 view**
(ngưỡng tùy chỉnh) thì bot gửi **link Reel** về Telegram — mỗi Reel chỉ báo **1 lần**.
Bạn điều khiển tool ngay trong Telegram: thêm/bỏ Page, đổi ngưỡng, xem top Reels…

Tool dùng **Facebook Graph API chính thức** (không scrape, không cookie, không proxy)
nên không làm tài khoản bị khóa.

> ⚠️ **Giới hạn quan trọng:** Facebook chỉ cho đọc số view (insights) của Reels thuộc
> **Page bạn là admin / có quyền quản lý**. Không lấy được view của Page người khác.

---

## Tính năng

- 🔁 Quét tự động (mặc định 2 phút/lần) các Reels đăng trong 7 ngày gần nhất
- 🔥 Báo về Telegram khi Reel vượt ngưỡng: tên Page, số view, đăng cách đây bao lâu, caption, link
- 🤖 Điều khiển bằng lệnh Telegram (xem bảng bên dưới)
- 💾 Ghi nhớ Reel đã báo (SQLite) → không bao giờ báo trùng, kể cả khi khởi động lại
- 🛡 Tự nghỉ 15 phút khi Facebook báo giới hạn tốc độ; tự thử lại khi mất mạng
- ⏰ Nhắc trước 7 ngày khi token Facebook sắp hết hạn, báo ngay khi token hỏng
- 🔒 Chỉ trả lời lệnh từ đúng chat bạn cấu hình — người lạ nhắn bot sẽ bị bỏ qua

## Lệnh Telegram

| Lệnh | Tác dụng |
|---|---|
| `/status` | Trạng thái: số Page, ngưỡng, lần quét gần nhất, hạn token |
| `/mypages` | Liệt kê các Page bạn quản lý (kèm ID để `/add`) |
| `/add <page_id>` | Thêm Page để theo dõi (thêm nhiều: `/add 111 222`) |
| `/remove <page_id>` | Bỏ theo dõi Page |
| `/pages` | Danh sách Page đang theo dõi |
| `/threshold 5000` | Đổi ngưỡng view (gõ `/threshold` để xem ngưỡng hiện tại) |
| `/top` | Top 10 Reels nhiều view nhất |
| `/scan` | Quét ngay, không đợi |
| `/help` | Danh sách lệnh |

---

## Bước 1 — Tạo Telegram bot

1. Mở Telegram, chat với **@BotFather** → gõ `/newbot` → đặt tên.
2. BotFather trả về **token** dạng `123456:ABC...` → đây là `TELEGRAM_BOT_TOKEN`.
3. Nhắn 1 tin bất kỳ cho bot vừa tạo (bấm **Start**).
4. Mở trình duyệt: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   → tìm `"chat":{"id":123456789` → số đó là `TELEGRAM_CHAT_ID`.
   (Muốn nhận trong group: thêm bot vào group, nhắn 1 tin trong group; id group là số âm.)

## Bước 2 — Lấy token Facebook

1. Vào <https://developers.facebook.com/> → **My Apps** → **Create App** (loại *Business*).
2. Mở **Graph API Explorer**: <https://developers.facebook.com/tools/explorer/>
3. Chọn app vừa tạo → **Generate Access Token** → tick các quyền:
   `pages_show_list`, `pages_read_engagement`, `read_insights`
4. Đổi sang **token dài hạn (60 ngày)**: dán token vào
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) → *Extend Access Token*.
5. Đây là `FB_USER_ACCESS_TOKEN`.

> 💡 Muốn token **không bao giờ hết hạn**: dùng *System User* trong Business Manager
> (Business Settings → Users → System Users → Generate Token với các quyền trên).

## Bước 3 — Chạy tool

Chọn **một** trong các cách sau.

### Cách A — Windows (dễ nhất)

1. Cài Python 3.10+ từ <https://www.python.org/downloads/> (nhớ tick **Add Python to PATH**).
2. Nhấp đúp `run_windows.bat`. Lần đầu nó tự cài thư viện và mở file `.env` →
   điền 3 dòng token từ Bước 1, 2 → lưu → nhấp đúp `run_windows.bat` lần nữa.
3. Telegram sẽ nhận tin "🚀 Reels Tracker đã chạy". Gõ `/mypages` rồi `/add <page_id>`.

Để cửa sổ mở thì tool chạy; tắt máy là tool dừng → muốn chạy 24/7 dùng Cách C.

### Cách B — macOS / Linux

```bash
cd reels_tracker
./run.sh          # lần đầu tạo file .env → điền token → chạy lại ./run.sh
```

### Cách C — Chạy 24/7 trên VPS bằng Docker (khuyên dùng)

```bash
cd reels_tracker
cp .env.example .env        # điền token
mkdir -p data
docker compose up -d --build
docker compose logs -f      # xem log
```

Docker tự khởi động lại tool khi lỗi hoặc khi VPS reboot. Dữ liệu nằm trong thư mục `data/`.

Không dùng Docker? Có file mẫu `deploy/reels-tracker.service` để chạy bằng systemd.

---

## Cấu hình

Cấu hình cơ bản nằm trong file **`.env`** (xem `.env.example`):

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token từ BotFather | bắt buộc |
| `TELEGRAM_CHAT_ID` | Chat/group nhận thông báo và được quyền ra lệnh | bắt buộc |
| `FB_USER_ACCESS_TOKEN` | Token Facebook (Bước 2) | bắt buộc |
| `FB_PAGE_IDS` | Page ID cách nhau dấu phẩy (hoặc dùng `/add`) | trống |
| `VIEW_THRESHOLD` | Ngưỡng view | `5000` |
| `POLL_INTERVAL_SECONDS` | Bao lâu quét 1 lần | `120` |

Tùy chọn nâng cao trong `config.json` (copy từ `config.example.json`, không bắt buộc):

| Khóa | Ý nghĩa | Mặc định |
|---|---|---|
| `pages` | `[{ "id", "name", "access_token"? }]` — `access_token` riêng nếu Page không thuộc token chính | `[]` |
| `max_reel_age_days` | Chỉ theo dõi Reels đăng trong N ngày | `7` |
| `token_warning_days` | Nhắc trước khi token hết hạn N ngày | `7` |
| `view_metrics` | Tên metric view, thử lần lượt | `fb_reels_total_plays`, `blue_reels_play_count` |
| `graph_api_version` | Phiên bản Graph API | `v23.0` |
| `db_path` | File database | `reels_tracker.db` |

Ngưỡng đổi bằng `/threshold` và Page thêm/bỏ bằng `/add` `/remove` được lưu trong
database, giữ nguyên sau khi khởi động lại.

> 🔒 **Không bao giờ commit `.env` hay `config.json`** lên GitHub — đã có sẵn trong `.gitignore`.

## Dòng lệnh

| Lệnh | Tác dụng |
|---|---|
| `python tracker.py` | Chạy liên tục (bot + quét) |
| `python tracker.py --test-telegram` | Gửi tin thử để kiểm tra Telegram |
| `python tracker.py --once` | Quét 1 lần rồi thoát (dùng với cron) |
| `python tracker.py --no-bot` | Chỉ quét, không nhận lệnh Telegram |
| `python tracker.py -v` | In log chi tiết để tìm lỗi |

## Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Không nhận được tin nào | Chạy `--test-telegram`. Kiểm tra đã bấm Start với bot chưa, chat ID đúng chưa. |
| `/add` báo "Không đọc được Page" | Tài khoản của token không phải admin Page đó, hoặc token thiếu quyền ở Bước 2. |
| Log báo `No view metric` | Chạy với `-v` để xem lỗi từng metric. Kiểm tra quyền `read_insights`. |
| Báo "Token không hợp lệ" | Token hết hạn/đổi mật khẩu → làm lại Bước 2, sửa `.env`, chạy lại tool. |
| Báo "giới hạn tốc độ" | Tool tự nghỉ 15 phút. Nếu bị thường xuyên: tăng `POLL_INTERVAL_SECONDS`. |
| Bot không trả lời lệnh | Chỉ chat có `TELEGRAM_CHAT_ID` mới được ra lệnh. Không chạy 2 bản tool cùng 1 bot. |

## Lưu ý thực tế

- Số view từ API có thể **trễ vài phút đến vài chục phút** so với số trên Facebook.
- Mỗi lần quét gọi API khoảng *(số Page + số Reels mới chưa báo)* lần. Reel đã báo
  sẽ không bị gọi lại nữa, nên rất tiết kiệm.

## Chạy test

```bash
pip install pytest
python -m pytest -q
```

## Cấu trúc code

| File | Vai trò |
|---|---|
| `tracker.py` | Chương trình chính: vòng lặp quét, gửi cảnh báo |
| `graph.py` | Gọi Facebook Graph API, xử lý rate limit / lỗi token |
| `telegram_bot.py` | Gửi tin Telegram và xử lý các lệnh `/...` |
| `store.py` | Database SQLite (Page, cài đặt, Reels, lịch sử đã báo) |
| `config.py` | Đọc `.env`, `config.json`, biến môi trường |
