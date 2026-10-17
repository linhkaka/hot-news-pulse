# ============================================================================
# RICHTUBE - Đoạn code CORS cần thêm vào main.py của Backend FastAPI
# Mục đích: cho phép Web Dashboard (cổng 3000) gọi API (cổng 8000).
#
# Cách dùng: chép 2 phần dưới vào main.py
#   - Phần 1: đặt cùng chỗ với các dòng import ở đầu file
#   - Phần 2: đặt NGAY SAU dòng tạo app, ví dụ: app = FastAPI(...)
# ============================================================================

# ---- Phần 1: import ----
import os
from fastapi.middleware.cors import CORSMiddleware

# ---- Phần 2: sau dòng `app = FastAPI(...)` ----
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(  # noqa: F821  (biến `app` đã có sẵn trong main.py)
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
