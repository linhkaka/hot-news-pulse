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

## Chạy bằng Docker

Từ thư mục gốc repo: `docker compose up --build`
