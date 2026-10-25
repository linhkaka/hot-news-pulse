# SNAKEMEDIA POD 2.0 — tiện ích Chrome (bản final)

Bản tiện ích Chrome của SNAKEMEDIA POD, **đủ chức năng như app** (`../snakemedia-pod`), chạy ngay trong Chrome của bạn:
không cần cài Python, không cần app chạy nền, dùng luôn tài khoản Facebook / TikTok đang đăng nhập.

Luật chấm nhãn, cách gom video và giao diện **giống hệt app** (bài kiểm thử so từng con số giữa 2 bản).
Hướng dẫn đầy đủ từng mục, luật chấm, Shopify, an toàn tài khoản: xem `../snakemedia-pod/README.md` — dưới đây chỉ ghi phần riêng của tiện ích.

---

## 1. Cài đặt (5 bước)

1. Tải **`SnakemediaPOD-Chrome.zip`** ở mục **Releases** của repo (bản `snakepod-v2.0.0`), giải nén ra 1 thư mục cố định,
   ví dụ `C:\SnakemediaPOD-Chrome`. **Đừng xoá thư mục này** — Chrome đọc tiện ích từ đó.
2. Mở Chrome, gõ `chrome://extensions` vào thanh địa chỉ.
3. Bật **Chế độ dành cho nhà phát triển** (Developer mode) ở góc trên bên phải.
4. Bấm **Tải tiện ích đã giải nén** (Load unpacked) → chọn thư mục ở bước 1 (thư mục có file `manifest.json`).
5. Bấm biểu tượng mảnh ghép 🧩 → ghim **SNAKEMEDIA POD**. Bảng điều khiển tự mở lần đầu.

**Cập nhật bản mới**: giải nén đè vào cùng thư mục → bấm ↻ (Tải lại) trên thẻ tiện ích ở `chrome://extensions`. Dữ liệu giữ nguyên.

**Khuyên dùng**: tạo 1 **hồ sơ Chrome riêng** (ảnh hồ sơ góc trên → Thêm), đăng nhập tài khoản Facebook / TikTok **phụ**
và cài tiện ích trong hồ sơ đó. Đừng quét bằng tài khoản chính.

## 2. Bắt đầu nhanh

1. Bấm biểu tượng tiện ích → **Mở bảng điều khiển**. Muốn xem thử: nút **Xem thử với dữ liệu mẫu** (lượt quét thật đầu tiên tự xoá dữ liệu mẫu).
2. **Quét từ khoá** → gõ từ khoá → **Quét**; hoặc tab **Pinterest / Google Trends / Tự đào** → tick nhiều từ → **Quét các từ đã chọn**.
3. Tiện ích mở **1 cửa sổ Chrome riêng**, cuộn rồi tự đóng. **Để cửa sổ đó hiện trên màn hình đến khi quét xong** —
   Chrome ngừng tải trang trong cửa sổ bị thu nhỏ / bị che hết (tiện ích ghi cảnh báo vào nhật ký nếu gặp).
4. Bảng **tiến độ** bên phải: đang quét việc thứ mấy, đã đọc bao nhiêu QC, còn bao lâu. Đóng trang bảng điều khiển vẫn quét tiếp (giữ Chrome mở).
5. Xem **Tổng quan → Video nổi bật** và các tab Sắp WIN / Video Win / Tiềm Năng / SP bò sữa → **📊 Phân tích**, **⧉ Clone**, **⬇ Tải**.

## 3. Riêng bản tiện ích

- **Tự lưu khi lướt** (mục Quét từ khoá): bạn tự mở Thư viện quảng cáo Facebook / TikTok / Creative Center và lướt,
  tiện ích lưu luôn các QC / video bạn đã xem (không tính vào giới hạn quét, không tự cuộn).
- **Tải ảnh / video** dùng trình tải của Chrome → thư mục **Tải về / SnakemediaPOD / <ngày>**.
- **Đăng nhập Facebook / TikTok / Pinterest**: đăng nhập thẳng trên Chrome này (mục Chế độ an toàn có nút mở trang đăng nhập).
- **Tự quét mỗi đêm** chỉ chạy khi Chrome đang mở vào giờ đó.

| | App (Windows) | Tiện ích Chrome |
|---|---|---|
| Cài | file `.exe` | Load unpacked |
| Trình duyệt quét | Chromium riêng của app | cửa sổ Chrome của bạn |
| Proxy (`proxy.txt`) | có | không (dùng proxy / VPN của máy) |
| Thông báo máy tính | Windows | của Chrome (Windows / macOS / Linux) |
| Tự lưu khi lướt | không | có |
| Dữ liệu nằm ở | `%LOCALAPPDATA%\SnakemediaPOD` | trong hồ sơ Chrome (**gỡ tiện ích là mất dữ liệu** — xuất file ở *Góp kho dữ liệu* trước) |

Chuyển dữ liệu giữa app và tiện ích: **⇄ Góp kho dữ liệu → Xuất** ở bên này, **Nhập** ở bên kia (cùng định dạng file).

## 4. An toàn & giới hạn

Tiện ích không che giấu việc tự động hoá (không giả dấu vân tay, không giải captcha, không xoay tài khoản); nó quét chậm,
giới hạn số lượt mỗi ngày (Facebook 40, TikTok 20, Pinterest 15) và **dừng ngay** khi gặp checkpoint / captcha / bắt đăng nhập.

- **Chưa thử trên Facebook / TikTok / Creative Center / Pinterest / Shopify thật** (môi trường phát triển bị chặn); mọi phần quét
  được kiểm thử trên trang giả. Ra 0 kết quả → **Chế độ an toàn → Gói chẩn đoán → Tải .zip** và gửi để sửa bộ đọc dữ liệu.
- Ảnh / mô tả clone từ shop khác và video tải về có bản quyền: chỉ dùng để nghiên cứu, sửa lại trước khi bán.
- Tự động thu thập dữ liệu có thể vi phạm điều khoản của Meta / TikTok / Pinterest. Bạn tự chịu trách nhiệm khi dùng.

---

## Cho lập trình viên

- Ngưỡng chấm nhãn, giới hạn an toàn, địa chỉ trang: `lib/config.js`. Từ khoá POD / niche: `lib/pod.js`.
  Sửa xong bấm ↻ ở `chrome://extensions`, rồi *Chấm lại* (hoặc quét lại).
- Giao diện là **1 file dùng chung với app**: sửa ở `snakemedia-pod/snakepod/static/` rồi chạy `python snakemedia-chrome/sync_ui.py`.

```
manifest.json        khai báo tiện ích (Manifest V3)
sw.js                phần nền: nhận lệnh (chỉ từ trang của tiện ích), hàng đợi quét, lịch tự quét
lib/                 logic chuyển từ bản Python: config, db (IndexedDB), fbparser, analyze, landing, pod, social,
                     safety, notify, diag, scanner (điều khiển cửa sổ quét), jobs, api, demo, media,
                     shopify (Clone), kwtrends (Pinterest / Google Trends)
content/hook.js      chạy trong trang Facebook / TikTok / Pinterest, sao chép phản hồi API dữ liệu (không sửa, không chặn)
content/agent.js     chuyển dữ liệu đó về phần nền
dashboard.*          bảng điều khiển (bản sao giao diện của app)
popup.*              cửa sổ nhỏ khi bấm biểu tượng tiện ích
tests/               kiểm thử bằng Chromium thật trên trang Facebook / TikTok / Pinterest / Shopify GIẢ
```

```
pip install -r ../snakemedia-pod/requirements.txt
python -m playwright install chromium
cd snakemedia-chrome && python -m pytest -v
```
