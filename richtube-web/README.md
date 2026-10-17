# RICHTUBE Studio Dashboard (SNAKEMEDIA)

Giao diện Command Center 3 cột: **Outlier Radar → Giải mã cấu trúc → Kịch bản sản xuất 4 cột**.
Next.js 14 (App Router) + Tailwind CSS + Lucide Icons.

## Chạy thử trên máy (cần Node.js 20+)

```bash
cd richtube-web
npm install
npm run dev
```

Mở trình duyệt: http://localhost:3000

## Kết nối Backend

Copy `.env.example` thành `.env.local` và sửa địa chỉ FastAPI nếu cần:

```
NEXT_PUBLIC_RICHTUBE_API_URL=http://localhost:8000
```

Nếu Backend chưa chạy, góc trên bên phải hiện **Engine: Offline (Demo)** và dashboard vẫn hiển thị dữ liệu mẫu.

API mà giao diện gọi:

| Nút | Endpoint |
|---|---|
| Spy Video | `POST /api/v1/spy/video` `{ video_url, notify_telegram }` |
| Tìm Kênh Đa Quốc Gia | `POST /api/v1/discover/channel` `{ seed_channel_url, target_markets }` |
| Đèn trạng thái Engine | `GET /health` |

## Bật CORS cho Backend (bắt buộc)

Trình duyệt sẽ chặn Web (cổng 3000) gọi sang API (cổng 8000) nếu Backend chưa bật CORS.
Chép đoạn code trong [`../backend-snippets/cors_main_patch.py`](../backend-snippets/cors_main_patch.py) vào `main.py`
(phần import ở đầu file, phần `app.add_middleware(...)` ngay sau dòng `app = FastAPI(...)`).

## Chạy cả hệ thống 24/7 bằng Docker

1. Đặt `docker-compose.yml` (ở thư mục gốc repo này) vào thư mục gốc dự án `richtube-snakemedia/`,
   cạnh `main.py`, `telegram_bot.py`, `Dockerfile` của Backend và thư mục `richtube-web/`.
2. Nếu tên file Bot/Backend khác, sửa dòng `command:` trong `docker-compose.yml`.
3. Chạy:

```bash
docker compose up -d --build
```

| Service | Cổng | Vai trò |
|---|---|---|
| `richtube-api` | 8000 | Backend Engine (FastAPI) |
| `richtube-bot` | – | Telegram Bot |
| `richtube-web` | 3000 | Web Dashboard |

Tất cả có `restart: unless-stopped`, nên tự chạy lại khi lỗi hoặc khi khởi động lại máy (Docker cần được bật tự khởi động).

**Chạy trên VPS:** tạo file `.env` cạnh `docker-compose.yml` với:

```
RICHTUBE_PUBLIC_API_URL=http://<IP-VPS>:8000
CORS_ORIGINS=http://<IP-VPS>:3000
```
