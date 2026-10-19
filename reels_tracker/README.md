# Reels & YouTube Tracker → Telegram

Tool chạy 24/7, tự động quét hệ thống **Facebook Fanpage** và **kênh YouTube**
**mỗi 30 phút** (đổi được thành 60 phút hoặc bất kỳ, bằng lệnh `/interval`). Video/Reel nào **vượt 5.000 view** (ngưỡng tùy chỉnh) thì bot gửi
**link chính xác** về Telegram — mỗi video chỉ báo **1 lần**.
Bạn điều khiển tool ngay trong Telegram: thêm/bỏ kênh, đổi ngưỡng, xem top video…

Tool chỉ dùng **nguồn chính thức** (YouTube RSS, YouTube Data API, Facebook Graph API):
không scrape, không cookie, không proxy → không làm tài khoản bị khóa.

| | YouTube | Facebook Reels |
|---|---|---|
| Cần gì | Không cần gì (RSS) — API key là tùy chọn | Token Facebook |
| Theo dõi được | Mọi kênh công khai | Chỉ Page bạn là admin / có quyền quản lý |
| Tần suất quét | 30 phút/lần (mặc định) | 30 phút/lần (mặc định) |

> ⏱ Đổi tần suất ngay trong Telegram: `/interval 30` (30 phút) hoặc `/interval 60` (1 giờ).
> Áp dụng cho cả Facebook và YouTube, giữ nguyên sau khi khởi động lại.
> Quét thưa như vậy gần như không tốn quota/API và không bao giờ bị giới hạn.

---

## Tính năng

- ⏱ Quét mỗi 30 phút (đổi bằng `/interval`), **nhiều Page/kênh song song** (mặc định 5 luồng)
- 📥 YouTube: phát hiện video mới bằng RSS miễn phí; có API key thì lấy số view
  của **50 video chỉ tốn 1 đơn vị quota** → theo dõi được hàng trăm kênh
- 🐢 Facebook: Reels mới (< 24 giờ) kiểm tra mỗi lần quét; Reels cũ hơn kiểm tra 10 phút/lần
  → tiết kiệm API, tránh bị giới hạn khi có nhiều Fanpage
- 🔥 Tin báo gồm: kênh/Page, tiêu đề hoặc caption, số view, đăng cách đây bao lâu, link
  (Shorts có link `/shorts/` chuẩn)
- 🤖 Điều khiển bằng lệnh Telegram; `/addall` thêm **tất cả** Fanpage bạn quản lý 1 lần
- 💾 Ghi nhớ video đã báo (SQLite) → không báo trùng, kể cả khi khởi động lại
- 🛡 Hết quota YouTube → tự nghỉ 1 giờ; Facebook giới hạn tốc độ → tự nghỉ 15 phút
- ⏰ Báo ngay khi API key / token hỏng, nhắc trước khi token Facebook hết hạn
- 🔒 Chỉ trả lời lệnh từ đúng chat bạn cấu hình — người lạ nhắn bot sẽ bị bỏ qua

## Lệnh Telegram

| Lệnh | Tác dụng |
|---|---|
| `/status` | Trạng thái: số kênh/Page, ngưỡng, lần quét gần nhất, quota |
| `/addyt <kênh>` | Thêm kênh YouTube: ID `UC...`, link kênh, hoặc `@handle` (cần API key). Thêm nhiều: `/addyt UCaaa UCbbb` |
| `/removeyt <channel_id>` | Bỏ theo dõi kênh YouTube |
| `/channels` | Danh sách kênh YouTube đang theo dõi (kèm ID) |
| `/addall` | Thêm **tất cả** Facebook Page bạn quản lý |
| `/mypages` | Liệt kê các Facebook Page bạn quản lý (kèm ID) |
| `/add <page_id>` | Thêm 1 Facebook Page (thêm nhiều: `/add 111 222`) |
| `/remove <page_id>` | Bỏ theo dõi Facebook Page |
| `/pages` | Danh sách Facebook Page đang theo dõi |
| `/threshold 5000` | Đổi ngưỡng view (dùng chung cho YouTube và Facebook) |
| `/interval 30` | Đổi thời gian giữa 2 lần quét, tính bằng phút (`/interval 60` = 1 giờ) |
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

## Bước 2a — YouTube

**Không cần làm gì** nếu dùng RSS miễn phí. Chỉ cần ID kênh:
mở kênh YouTube → bấm vào phần mô tả kênh (*…thêm*) → **Chia sẻ kênh** →
**Sao chép mã kênh**. ID có dạng `UCxxxxxxxxxxxxxxxxxxxxxx`.

**Nên có API key (miễn phí)** để số view cập nhật nhanh hơn và thêm kênh bằng `@handle`:

1. Vào <https://console.cloud.google.com/> → đăng nhập Google → tạo **Project** mới.
2. **APIs & Services → Library** → tìm **YouTube Data API v3** → **Enable**.
3. **APIs & Services → Credentials** → **Create credentials → API key**.
4. Copy key → đây là `YOUTUBE_API_KEY`. (Nên bấm *Restrict key* → chỉ cho *YouTube Data API v3*.)

Quota miễn phí 10.000 đơn vị/ngày. Mỗi lần quét tốn khoảng **1 đơn vị cho mỗi 50 video**
đang theo dõi → quét 30 phút/lần chỉ tốn khoảng 50–200 đơn vị/ngày. `/status` cho biết
quota đã dùng hôm nay.

## Bước 2b — Facebook (nếu theo dõi Fanpage)

1. Vào <https://developers.facebook.com/> → **My Apps** → **Create App** (loại *Business*).
2. Mở **Graph API Explorer**: <https://developers.facebook.com/tools/explorer/>
3. Chọn app vừa tạo → **Generate Access Token** → tick các quyền:
   `pages_show_list`, `pages_read_engagement`, `read_insights`
4. Đổi sang **token dài hạn (60 ngày)**: dán token vào
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) → *Extend Access Token*.
5. Đây là `FB_USER_ACCESS_TOKEN`. Chạy tool xong gõ `/addall` để theo dõi mọi Page bạn quản lý.

> 💡 **Hệ thống nhiều Fanpage:** dùng *System User* trong Business Manager — token
> **không bao giờ hết hạn** và gán được cho tất cả Page của doanh nghiệp
> (Business Settings → Users → System Users → thêm Page → Generate Token với các quyền trên).
>
> Page của đối tác: nhờ họ thêm tài khoản bạn làm người quản lý (vai trò *Analyst* trở lên).

## Bước 3 — Chạy tool

Chọn **một** trong các cách sau.

### Cách A — Windows (dễ nhất)

1. Cài Python 3.10+ từ <https://www.python.org/downloads/> (nhớ tick **Add Python to PATH**).
2. Nhấp đúp `run_windows.bat`. Lần đầu nó tự cài thư viện và mở file `.env` →
   điền token → lưu → nhấp đúp `run_windows.bat` lần nữa.
3. Telegram sẽ nhận tin "🚀 Tracker đã chạy". Gõ `/addyt UC...` và/hoặc `/addall`.

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
Một VPS rẻ nhất (1 CPU, 1 GB RAM) là đủ.

Không dùng Docker? Có file mẫu `deploy/reels-tracker.service` để chạy bằng systemd.

---

## Cấu hình

Cấu hình cơ bản nằm trong file **`.env`** (xem `.env.example`):

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token từ BotFather | bắt buộc |
| `TELEGRAM_CHAT_ID` | Chat/group nhận thông báo và được quyền ra lệnh | bắt buộc |
| `YOUTUBE_API_KEY` | API key YouTube (Bước 2a) | trống = chỉ dùng RSS |
| `YT_CHANNELS` | Kênh YouTube, cách nhau dấu phẩy (hoặc dùng `/addyt`) | trống |
| `YOUTUBE_POLL_INTERVAL_SECONDS` | Bao lâu quét YouTube 1 lần (giây) | `1800` (30 phút) |
| `FB_USER_ACCESS_TOKEN` | Token Facebook (Bước 2b) | trống = tắt Facebook |
| `FB_PAGE_IDS` | Page ID cách nhau dấu phẩy (hoặc dùng `/addall`, `/add`) | trống |
| `POLL_INTERVAL_SECONDS` | Bao lâu quét Facebook 1 lần (giây) | `1800` (30 phút) |
| `VIEW_THRESHOLD` | Ngưỡng view | `5000` |
| `WORKERS` | Số Page/kênh quét song song | `5` |

Tùy chọn nâng cao trong `config.json` (copy từ `config.example.json`, không bắt buộc):

| Khóa | Ý nghĩa | Mặc định |
|---|---|---|
| `youtube_channels` | Danh sách kênh YouTube | `[]` |
| `pages` | `[{ "id", "name", "access_token"? }]` — `access_token` riêng nếu Page không thuộc token chính | `[]` |
| `max_reel_age_days` | Chỉ theo dõi video/Reels đăng trong N ngày | `7` |
| `fresh_hours` | Reels mới hơn N giờ được kiểm tra mỗi lần quét | `24` |
| `slow_check_interval_seconds` | Reels cũ hơn kiểm tra cách nhau bao lâu | `600` |
| `token_warning_days` | Nhắc trước khi token Facebook hết hạn N ngày | `7` |
| `view_metrics` | Tên metric view Facebook, thử lần lượt | `fb_reels_total_plays`, `blue_reels_play_count` |
| `graph_api_version` | Phiên bản Facebook Graph API | `v23.0` |
| `db_path` | File database | `reels_tracker.db` |

Ngưỡng đổi bằng `/threshold`, thời gian quét đổi bằng `/interval`, kênh/Page thêm bỏ bằng
lệnh Telegram được lưu trong database, giữ nguyên sau khi khởi động lại (và được ưu tiên
hơn giá trị trong `.env`).

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
| `/addyt @handle` báo cần API key | Không có key thì dùng ID kênh `UC...` (cách lấy ở Bước 2a). |
| `/addyt` báo "Không tìm thấy kênh" | Kiểm tra lại ID / @handle. |
| Muốn kiểm tra ngay, không đợi 30 phút | Gõ `/scan`. |
| Số view YouTube cập nhật chậm | RSS có thể trễ. Thêm `YOUTUBE_API_KEY` để có số mới hơn. |
| Báo "YouTube API key không dùng được" | Kiểm tra key, và đã **Enable YouTube Data API v3** chưa (Bước 2a). |
| Báo "hết quota YouTube" | Tool tự nghỉ 1 giờ. Tăng thời gian quét bằng `/interval`. Quota reset mỗi ngày. |
| `/add` báo "Không đọc được Page" | Tài khoản của token không phải admin Page đó, hoặc token thiếu quyền ở Bước 2b. |
| Log báo `No view metric` (Facebook) | Chạy với `-v` để xem lỗi từng metric. Kiểm tra quyền `read_insights`. |
| Báo "Token Facebook không hợp lệ" | Token hết hạn/đổi mật khẩu → làm lại Bước 2b, sửa `.env`, chạy lại tool. |
| Báo "giới hạn tốc độ" (Facebook) | Tool tự nghỉ 15 phút. Nếu bị thường xuyên: tăng thời gian quét bằng `/interval` hoặc giảm `WORKERS`. |
| Bot không trả lời lệnh | Chỉ chat có `TELEGRAM_CHAT_ID` mới được ra lệnh. Không chạy 2 bản tool cùng 1 bot. |

## Lưu ý thực tế

- RSS YouTube chỉ chứa **15 video mới nhất** của mỗi kênh. Kênh đăng hơn 15 video/tuần:
  có API key thì tool tự lấy thêm qua API; không có key thì video cũ hơn sẽ bị bỏ qua.
- Video đã báo không bị gọi lại nữa, nên rất tiết kiệm quota/API.
- Video "sắp công chiếu" (premiere chưa diễn ra) được bỏ qua cho đến khi lên sóng.

## Chạy test

```bash
pip install pytest
python -m pytest -q
```

## Cấu trúc code

| File | Vai trò |
|---|---|
| `tracker.py` | Chương trình chính: vòng lặp quét, quét song song các Fanpage |
| `youtube.py` | YouTube RSS + Data API, quét kênh, gửi cảnh báo YouTube |
| `graph.py` | Gọi Facebook Graph API, xử lý rate limit / lỗi token |
| `telegram_bot.py` | Gửi tin Telegram và xử lý các lệnh `/...` |
| `store.py` | Database SQLite (Page, kênh, cài đặt, video, lịch sử đã báo) |
| `config.py` | Đọc `.env`, `config.json`, biến môi trường |
| `net.py` | Kết nối HTTP riêng cho từng luồng quét |
