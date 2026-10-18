# RICHTUBE Engine (Backend) — SNAKEMEDIA

FastAPI + Telegram Bot. Nhận link video/kênh YouTube và tự làm các bước:

1. **Market Signal (vidIQ Engine)**: tính VPH hiện tại so với VPH trung vị của kênh (baseline), ra điểm **TAE** (số lần đột biến).
2. **Deep Anatomy (Nevlex Engine)**: lấy Most Replayed Heatmap, transcript có timecode và top bình luận.
   Gemini "xem" 2 phút đầu video và mổ xẻ Hook, Bao bì, nhịp kể chuyện, lỗ hổng khán giả.
3. **Production Blueprint**: 3 tiêu đề, prompt thumbnail và kịch bản phân cảnh 4 cột (Voiceover · Visual · AI Prompt · SFX).
4. **Đồng bộ**: lưu kết quả, đẩy sang **Lark Base** và gửi **Telegram**.
5. **Radar 24/7**: theo dõi danh sách kênh, cứ `RADAR_INTERVAL_HOURS` giờ lại quét video mới.
   Video nào có TAE ≥ `RADAR_MIN_TAE` thì tự mổ xẻ và báo về Telegram.

## 1. Chuẩn bị key

| Key | Lấy ở đâu |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console → bật **YouTube Data API v3** → Credentials → API key |
| `GEMINI_API_KEYS` | https://aistudio.google.com/apikey — có thể nhập nhiều key, cách nhau dấu phẩy |
| `TELEGRAM_BOT_TOKEN` | Chat với **@BotFather** → `/newbot` |
| `TELEGRAM_CHAT_ID` | Chạy bot, nhắn `/id` cho bot để xem |
| `LARK_*` | Lark Developer Console → tạo Custom App → cấp quyền `bitable:app`, thêm App vào Base |

Copy `.env.example` thành `.env` rồi điền giá trị.

## 2. Bảng Lark Base

Tạo bảng có **đúng các cột sau** (sai tên cột thì Lark từ chối ghi, nhưng kết quả vẫn được lưu trong Engine):

| Tên cột | Kiểu |
|---|---|
| Video ID | Text |
| Tiêu đề gốc | Text |
| Kênh | Text |
| Thị trường | Text |
| Link | Text |
| TAE | Number |
| VPH | Number |
| Baseline VPH | Number |
| Góc khai thác | Text |
| Tiêu đề đề xuất | Text |
| Prompt Thumbnail | Text |
| Kịch bản | Text |

`LARK_BASE_APP_TOKEN` và `LARK_TABLE_ID` nằm trong link Base:
`https://xxx.larksuite.com/base/<APP_TOKEN>?table=<TABLE_ID>`.
Nếu dùng Feishu (Trung Quốc), đặt `LARK_DOMAIN=https://open.feishu.cn`.

## 3. Chạy

**Bằng Docker (khuyên dùng, chạy 24/7):** ở thư mục gốc repo:

```bash
docker compose up -d --build
```

**Chạy tay để thử:**

```bash
cd richtube-engine
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --port 8000          # cửa sổ 1: Engine
python telegram_bot.py                # cửa sổ 2: Bot
```

Tài liệu API tự động: http://localhost:8000/docs

## 4. API

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/health` | Trạng thái, số Gemini key, đã cấu hình YouTube/Lark/Telegram chưa |
| GET | `/api/v1/outliers?market=US` | Danh sách video đã phân tích |
| GET | `/api/v1/outliers/{video_id}` | Chi tiết 1 video |
| POST | `/api/v1/spy/video` | `{ "video_url": "...", "notify_telegram": true }` → trả về job (chạy nền) |
| POST | `/api/v1/discover/channel` | `{ "seed_channel_url": "...", "target_markets": ["US","JP"] }` → job |
| GET | `/api/v1/jobs/{job_id}` | Tiến độ: `queued` / `running` / `done` / `failed` |
| POST | `/api/v1/outliers/{video_id}/sync-lark` | Đồng bộ lại 1 video sang Lark Base |
| POST | `/api/v1/outliers/{video_id}/reanalyze` | Phân tích lại với số liệu mới → job |
| DELETE | `/api/v1/outliers/{video_id}` | Xoá video khỏi Dashboard |
| GET | `/api/v1/outliers/{video_id}/export.md` · `.csv` | Tải kịch bản cho Biên kịch / Editor |
| GET | `/api/v1/watchlist` | Danh sách kênh Radar đang theo dõi |
| POST | `/api/v1/watchlist` | `{ "channel_url": "..." }` thêm kênh |
| DELETE | `/api/v1/watchlist/{channel_id}` | Bỏ theo dõi |
| POST | `/api/v1/radar/run` | Quét Radar ngay → job |
| POST | `/api/v1/outliers/import` | Nhận kết quả đã phân tích từ Tiện ích Chrome → lưu, đồng bộ Lark, báo Telegram |

Nếu đặt `RICHTUBE_API_KEY`, các lệnh POST/DELETE phải gửi kèm header `X-API-Key` (Web và Bot tự gửi).

## 5. Lệnh Telegram Bot

`/spy <link video>` · `/discover <link kênh>` · `/watch <link kênh>` · `/watchlist` · `/unwatch <số>` · `/radar` · `/top` · `/status` · `/id` · hoặc dán thẳng link video.

Chỉ những chat có trong `TELEGRAM_CHAT_ID` / `TELEGRAM_ALLOWED_CHAT_IDS` mới ra lệnh được.

## 6. Lưu ý quan trọng

- **TAE** = VPH hiện tại ÷ VPH trung vị của ~20 video gần nhất trên kênh. Đây là số ước tính, YouTube không công khai lượt xem đến từ quảng cáo.
- **Heatmap & Transcript** không có trong API chính thức, nên Engine đọc từ trang YouTube theo kiểu *best-effort*.
  Video không có "Most Replayed" (video mới, ít view) hoặc YouTube chặn IP máy chủ thì phần này để trống, các phần khác vẫn chạy.
- **Quota YouTube** (10.000 đơn vị/ngày miễn phí): 1 lệnh Spy tốn khoảng 5 đơn vị. 1 lệnh Discover 6 thị trường tốn khoảng 700 đơn vị (mỗi lượt tìm kiếm tốn 100).
  Radar tốn khoảng 3 đơn vị cho mỗi kênh mỗi lượt quét (50 kênh × 4 lượt/ngày ≈ 600 đơn vị), cộng thêm phần mổ xẻ video đột biến.
- **Bảo mật:** nếu mở cổng 8000 ra Internet, hãy đặt `RICHTUBE_API_KEY` để người lạ không dùng hết quota của bạn.

## 7. Kiểm thử

```bash
pip install -r requirements-dev.txt
pytest
```
