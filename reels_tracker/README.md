# Reels & YouTube Tracker → Telegram

Tool chạy 24/7, theo dõi **video YouTube** trên các kênh của bạn và **Reels** trên các
Facebook Page bạn quản lý. Video/Reel nào **vượt 5.000 view** (ngưỡng tùy chỉnh) thì bot
gửi **link chính xác** về Telegram — mỗi video chỉ báo **1 lần**.
Bạn điều khiển tool ngay trong Telegram: thêm/bỏ kênh, đổi ngưỡng, xem top video…

Bạn có thể dùng **chỉ YouTube**, **chỉ Facebook**, hoặc **cả hai**.

Tool chỉ dùng **API chính thức** (YouTube Data API, Facebook Graph API): không scrape,
không cookie, không proxy → không làm tài khoản bị khóa.

> ℹ️ **YouTube:** chỉ cần một API key miễn phí, đọc được số view công khai của mọi video.
> **Facebook:** chỉ đọc được view Reels của **Page bạn là admin / có quyền quản lý**.

---

## Tính năng

- 🔁 Quét tự động: YouTube 5 phút/lần, Facebook 2 phút/lần (chỉnh được)
- 🎯 Chỉ theo dõi video/Reels đăng trong 7 ngày gần nhất
- 🔥 Tin báo gồm: kênh/Page, tiêu đề hoặc caption, số view, đăng cách đây bao lâu, link
- 🤖 Điều khiển bằng lệnh Telegram (bảng bên dưới)
- 💾 Ghi nhớ video đã báo (SQLite) → không báo trùng, kể cả khi khởi động lại
- 🛡 Hết quota YouTube → tự nghỉ 1 giờ; Facebook giới hạn tốc độ → tự nghỉ 15 phút
- ⏰ Báo ngay khi API key / token hỏng, nhắc trước khi token Facebook hết hạn
- 🔒 Chỉ trả lời lệnh từ đúng chat bạn cấu hình — người lạ nhắn bot sẽ bị bỏ qua

## Lệnh Telegram

| Lệnh | Tác dụng |
|---|---|
| `/status` | Trạng thái: số kênh/Page, ngưỡng, lần quét gần nhất, quota |
| `/addyt @handle` | Thêm kênh YouTube (dùng @handle, ID `UC...` hoặc link kênh) |
| `/removeyt <channel_id>` | Bỏ theo dõi kênh YouTube |
| `/channels` | Danh sách kênh YouTube đang theo dõi (kèm ID) |
| `/mypages` | Liệt kê các Facebook Page bạn quản lý (kèm ID để `/add`) |
| `/add <page_id>` | Thêm Facebook Page (thêm nhiều: `/add 111 222`) |
| `/remove <page_id>` | Bỏ theo dõi Facebook Page |
| `/pages` | Danh sách Facebook Page đang theo dõi |
| `/threshold 5000` | Đổi ngưỡng view (dùng chung cho YouTube và Facebook) |
| `/top` | Top 10 video/Reels nhiều view nhất |
| `/scan` | Quét ngay, không đợi |
| `/help` | Danh sách lệnh |

---

## Bước 1 — Tạo Telegram bot (bắt buộc)

1. Mở Telegram, chat với **@BotFather** → gõ `/newbot` → đặt tên.
2. BotFather trả về **token** dạng `123456:ABC...` → đây là `TELEGRAM_BOT_TOKEN`.
3. Nhắn 1 tin bất kỳ cho bot vừa tạo (bấm **Start**).
4. Mở trình duyệt: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   → tìm `"chat":{"id":123456789` → số đó là `TELEGRAM_CHAT_ID`.
   (Muốn nhận trong group: thêm bot vào group, nhắn 1 tin trong group; id group là số âm.)

## Bước 2a — Lấy YouTube API key (nếu theo dõi YouTube)

1. Vào <https://console.cloud.google.com/> → đăng nhập Google → tạo **Project** mới.
2. Vào **APIs & Services → Library** → tìm **YouTube Data API v3** → bấm **Enable**.
3. Vào **APIs & Services → Credentials** → **Create credentials → API key**.
4. Copy key → đây là `YOUTUBE_API_KEY`.
   (Nên bấm *Restrict key* → chỉ cho phép *YouTube Data API v3* để an toàn hơn.)

Miễn phí 10.000 đơn vị quota/ngày. Mỗi kênh tốn ~2 đơn vị/lần quét → quét 5 phút/lần
theo dõi được khoảng **15 kênh**. Nhiều kênh hơn thì tăng `YOUTUBE_POLL_INTERVAL_SECONDS`
(ví dụ 600 giây → ~30 kênh). Lệnh `/status` hiện ước tính quota đang dùng.

**Tìm @handle kênh:** mở kênh YouTube → phần chữ `@...` dưới tên kênh, hoặc trong link
`youtube.com/@ten_kenh`.

## Bước 2b — Lấy token Facebook (nếu theo dõi Facebook Reels)

1. Vào <https://developers.facebook.com/> → **My Apps** → **Create App** (loại *Business*).
2. Mở **Graph API Explorer**: <https://developers.facebook.com/tools/explorer/>
3. Chọn app vừa tạo → **Generate Access Token** → tick các quyền:
   `pages_show_list`, `pages_read_engagement`, `read_insights`
4. Đổi sang **token dài hạn (60 ngày)**: dán token vào
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) → *Extend Access Token*.
5. Đây là `FB_USER_ACCESS_TOKEN`.

> 💡 Muốn token Facebook **không bao giờ hết hạn**: dùng *System User* trong Business Manager
> (Business Settings → Users → System Users → Generate Token với các quyền trên).

## Bước 3 — Chạy tool

Chọn **một** trong các cách sau.

### Cách A — Windows (dễ nhất)

1. Cài Python 3.10+ từ <https://www.python.org/downloads/> (nhớ tick **Add Python to PATH**).
2. Nhấp đúp `run_windows.bat`. Lần đầu nó tự cài thư viện và mở file `.env` →
   điền token Telegram + YouTube key (và/hoặc token Facebook) → lưu →
   nhấp đúp `run_windows.bat` lần nữa.
3. Telegram sẽ nhận tin "🚀 Tracker đã chạy". Gõ `/addyt @kenh_cua_ban`.

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
| `YOUTUBE_API_KEY` | API key YouTube (Bước 2a) | trống = tắt YouTube |
| `YT_CHANNELS` | Kênh YouTube, cách nhau dấu phẩy (hoặc dùng `/addyt`) | trống |
| `YOUTUBE_POLL_INTERVAL_SECONDS` | Bao lâu quét YouTube 1 lần | `300` |
| `FB_USER_ACCESS_TOKEN` | Token Facebook (Bước 2b) | trống = tắt Facebook |
| `FB_PAGE_IDS` | Page ID cách nhau dấu phẩy (hoặc dùng `/add`) | trống |
| `POLL_INTERVAL_SECONDS` | Bao lâu quét Facebook 1 lần | `120` |
| `VIEW_THRESHOLD` | Ngưỡng view | `5000` |

Cần có ít nhất `YOUTUBE_API_KEY` hoặc `FB_USER_ACCESS_TOKEN`.

Tùy chọn nâng cao trong `config.json` (copy từ `config.example.json`, không bắt buộc):

| Khóa | Ý nghĩa | Mặc định |
|---|---|---|
| `youtube_channels` | Danh sách kênh YouTube | `[]` |
| `pages` | `[{ "id", "name", "access_token"? }]` — `access_token` riêng nếu Page không thuộc token chính | `[]` |
| `max_reel_age_days` | Chỉ theo dõi video/Reels đăng trong N ngày | `7` |
| `token_warning_days` | Nhắc trước khi token Facebook hết hạn N ngày | `7` |
| `view_metrics` | Tên metric view Facebook, thử lần lượt | `fb_reels_total_plays`, `blue_reels_play_count` |
| `graph_api_version` | Phiên bản Facebook Graph API | `v23.0` |
| `db_path` | File database | `reels_tracker.db` |

Ngưỡng đổi bằng `/threshold`, kênh/Page thêm bỏ bằng lệnh Telegram được lưu trong
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
| Báo "YouTube API key không dùng được" | Kiểm tra key, và đã **Enable YouTube Data API v3** chưa (Bước 2a). |
| `/addyt` báo "Không tìm thấy kênh" | Kiểm tra lại @handle (có trong link kênh), hoặc dùng ID kênh `UC...`. |
| Báo "hết quota YouTube" | Tool tự nghỉ 1 giờ. Tăng `YOUTUBE_POLL_INTERVAL_SECONDS` hoặc bớt kênh. Quota reset mỗi ngày. |
| `/add` báo "Không đọc được Page" | Tài khoản của token không phải admin Page đó, hoặc token thiếu quyền ở Bước 2b. |
| Log báo `No view metric` (Facebook) | Chạy với `-v` để xem lỗi từng metric. Kiểm tra quyền `read_insights`. |
| Báo "Token Facebook không hợp lệ" | Token hết hạn/đổi mật khẩu → làm lại Bước 2b, sửa `.env`, chạy lại tool. |
| Bot không trả lời lệnh | Chỉ chat có `TELEGRAM_CHAT_ID` mới được ra lệnh. Không chạy 2 bản tool cùng 1 bot. |

## Lưu ý thực tế

- Số view YouTube từ API thường được cập nhật sau vài phút; số view Reels Facebook có
  thể trễ vài phút đến vài chục phút.
- Video đã báo sẽ không bị gọi API lại nữa, nên rất tiết kiệm quota.
- Video "sắp công chiếu" (premiere chưa diễn ra) được bỏ qua cho đến khi lên sóng.

## Chạy test

```bash
pip install pytest
python -m pytest -q
```

## Cấu trúc code

| File | Vai trò |
|---|---|
| `tracker.py` | Chương trình chính: vòng lặp quét, gửi cảnh báo Facebook |
| `youtube.py` | Gọi YouTube Data API, quét kênh, gửi cảnh báo YouTube |
| `graph.py` | Gọi Facebook Graph API, xử lý rate limit / lỗi token |
| `telegram_bot.py` | Gửi tin Telegram và xử lý các lệnh `/...` |
| `store.py` | Database SQLite (Page, kênh, cài đặt, video, lịch sử đã báo) |
| `config.py` | Đọc `.env`, `config.json`, biến môi trường |
