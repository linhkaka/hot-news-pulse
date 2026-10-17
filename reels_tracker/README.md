# Reels Tracker → Telegram

Tool tự động theo dõi Reels của các Facebook Page, khi Reel nào **vượt 5.000 view**
thì gửi link Reel đó về Telegram (mỗi Reel chỉ gửi **1 lần**).

Tool dùng **Facebook Graph API chính thức** (không scrape, không cần cookie/proxy),
nên an toàn cho tài khoản.

> ⚠️ **Giới hạn quan trọng:** Facebook chỉ cho xem số view (insights) của Reels
> thuộc **Page mà bạn là admin/có quyền quản lý**. Không lấy được view của Page người khác.

---

## Cách hoạt động

```
Danh sách Page  →  cứ 2 phút quét 1 lần  →  lấy Reels đăng trong 7 ngày gần nhất
     →  đọc số view qua API  →  ≥ 5000 và chưa gửi?  →  gửi link về Telegram
                                                       →  ghi vào DB để không gửi lặp
```

---

## Bước 1 — Tạo Telegram bot

1. Mở Telegram, chat với **@BotFather** → gõ `/newbot` → đặt tên.
2. BotFather trả về **token** dạng `123456:ABC...` → đây là `telegram_bot_token`.
3. Nhắn 1 tin bất kỳ cho bot vừa tạo (bấm Start).
4. Mở trình duyệt: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   → tìm `"chat":{"id": 123456789` → số đó là `telegram_chat_id`.
   (Muốn gửi vào group: thêm bot vào group, nhắn 1 tin trong group, id sẽ là số âm.)

## Bước 2 — Lấy Facebook access token

1. Vào <https://developers.facebook.com/> → **My Apps** → **Create App** (loại *Business*).
2. Mở **Graph API Explorer** (<https://developers.facebook.com/tools/explorer/>).
3. Chọn app vừa tạo, bấm **Generate Access Token**, tick các quyền:
   - `pages_show_list`
   - `pages_read_engagement`
   - `read_insights`
4. Copy token → đổi sang **token dài hạn** (60 ngày) bằng
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) → nút *Extend Access Token*.
5. Dán vào `user_access_token`. Tool sẽ tự lấy token riêng của từng Page bạn quản lý.

**Lấy Page ID:** vào Page → *Giới thiệu (About)* → *Minh bạch trang* → Page ID.

## Bước 3 — Cài và chạy

```bash
cd reels_tracker
pip install -r requirements.txt
cp config.example.json config.json   # rồi mở config.json điền thông tin
python tracker.py --test-telegram    # kiểm tra bot gửi tin được chưa
python tracker.py                    # chạy liên tục
```

Các lệnh khác:

| Lệnh | Tác dụng |
|---|---|
| `python tracker.py --once` | Quét 1 lần rồi thoát (dùng với cron) |
| `python tracker.py -v` | In log chi tiết để debug |
| `python tracker.py --config khac.json` | Dùng file config khác |

## Cấu hình (`config.json`)

| Khóa | Ý nghĩa | Mặc định |
|---|---|---|
| `user_access_token` | Token Facebook dài hạn | — |
| `pages` | Danh sách `{ "id", "name", "access_token"? }` | — |
| `telegram_bot_token` | Token từ BotFather | — |
| `telegram_chat_id` | Chat/group nhận thông báo | — |
| `view_threshold` | Ngưỡng view | `5000` |
| `poll_interval_seconds` | Bao lâu quét 1 lần | `120` |
| `max_reel_age_days` | Chỉ theo dõi Reels mới đăng trong N ngày | `7` |
| `view_metrics` | Tên metric view, thử lần lượt | `fb_reels_total_plays`, `blue_reels_play_count` |
| `graph_api_version` | Phiên bản Graph API | `v23.0` |

> 🔒 **Không commit `config.json`** lên GitHub — trong đó có token bí mật
> (file đã được thêm vào `.gitignore`).

## Lưu ý thực tế

- Số view từ API có thể **trễ vài phút đến vài chục phút** so với số hiển thị trên Facebook.
- Mỗi lần quét gọi API khoảng *(số Page + số Reels mới)* lần. Nếu nhiều Page, tăng
  `poll_interval_seconds` hoặc giảm `max_reel_age_days` để tránh bị rate limit.
- Token dài hạn hết hạn sau ~60 ngày → cần làm lại Bước 2 (hoặc dùng System User token
  của Business Manager, loại này không hết hạn).
- Nếu log báo `No view metric`, thử chạy với `-v` để xem lỗi của từng metric.

## Chạy test

```bash
pip install pytest
python -m pytest -q
```
