# RICHTUBE OS — Công ty TNHH SNAKEMEDIA

Hệ thống do thám YouTube đa thị trường và sản xuất kịch bản 4 cột tự động.

```
.
├── docker-compose.yml   # Chạy cả 3 service 24/7
├── richtube-engine/     # Backend FastAPI (cổng 8000) + Telegram Bot
├── richtube-web/        # Web Dashboard Next.js (cổng 3000)
└── richtube-chrome/     # Tiện ích Chrome: nút 🔥 Spy ngay trên YouTube
```

## Khởi động nhanh (cần Docker)

```bash
git clone https://github.com/linhkaka/hot-news-pulse.git
cd hot-news-pulse
cp richtube-engine/.env.example richtube-engine/.env    # rồi mở file .env và điền key
docker compose up -d --build
```

- Web Dashboard: http://localhost:3000
- API + tài liệu: http://localhost:8000/docs
- Telegram: nhắn `/start` cho bot của bạn

**Tính năng chính:** Spy video outlier · Tìm đối thủ 6 thị trường · Radar 24/7 tự quét kênh theo dõi ·
Biểu đồ sóng giữ chân · Kịch bản 4 cột (tải .md / .csv) · Đồng bộ Lark Base · Telegram Bot.

Xem log: `docker compose logs -f` · Dừng: `docker compose down`

### Chạy trên VPS

Tạo file `.env` ở thư mục gốc (cạnh `docker-compose.yml`):

```
RICHTUBE_PUBLIC_API_URL=http://<IP-VPS>:8000
```

và trong `richtube-engine/.env` thêm `CORS_ORIGINS=http://<IP-VPS>:3000` và `RICHTUBE_API_KEY=<chuỗi bí mật>`.
Nếu đặt `RICHTUBE_API_KEY`, ghi cùng giá trị đó vào file `.env` ở thư mục gốc để Web gửi kèm key.

## Chỉ muốn dùng nhanh? Cài Tiện ích Chrome

Không cần Docker hay server: cài thư mục `richtube-chrome` vào Chrome, nhập Gemini key là dùng được.
Xem hướng dẫn tại [richtube-chrome/README.md](richtube-chrome/README.md).

Chi tiết từng phần: [richtube-engine/README.md](richtube-engine/README.md) · [richtube-web/README.md](richtube-web/README.md) · [richtube-chrome/README.md](richtube-chrome/README.md)
