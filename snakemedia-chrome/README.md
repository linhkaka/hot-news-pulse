# SNAKEMEDIA POD — tiện ích Chrome

Bản tiện ích Chrome của SNAKEMEDIA POD, đủ chức năng như app (`../snakemedia-pod`), chạy ngay trong Chrome của bạn:
không cần cài Python, không cần app chạy nền.

- **Quét QC Facebook** theo từ khoá (Thư viện quảng cáo, chỉ QC video, cả QC đã tắt) → gom QC cùng 1 video
  (dHash ảnh + collation + cùng nội dung/cùng sản phẩm) → đọc tuổi trang bán → chấm nhãn
  **Sắp WIN / Video Win / Video scale / Trang bán cũ / Video già** bằng luật rõ ràng, không có "điểm AI".
- **POD**: loại sản phẩm, niche, hàng cá nhân hoá, app POD trên trang bán; bảng **Niche POD**.
- **Video viral**: TikTok (tìm kiếm / #hashtag), TikTok Top Ads (Creative Center), Facebook Reels (thử nghiệm);
  nhãn Đang nổ / Viral / Đang lên theo lượt xem mỗi giờ. **QC đang lan nhanh** (nhiều QC/shop mới trong 48 giờ).
- **Theo dõi page/shop**, **Kho shop**, **Đào sâu** 1 video, **Tự quét mỗi đêm** (mặc định 1h sáng).
- **Chế độ an toàn**: nghỉ giữa các lượt, giới hạn lượt/ngày, cuộn chậm, gặp checkpoint/captcha/bắt đăng nhập
  thì dừng ngay và tạm dừng nền tảng đó. **Gói chẩn đoán** (.zip) khi quét ra 0 kết quả hoặc lỗi.
- **Thông báo**: Telegram + thông báo góc màn hình của Chrome.
- **Riêng bản tiện ích — Tự lưu khi lướt**: bạn tự mở Thư viện quảng cáo Facebook / TikTok / Creative Center
  và lướt, tiện ích lưu luôn các QC / video bạn đã xem (không tính vào giới hạn quét).

Luật chấm và cách gom video giống hệt app: bài kiểm thử `tests/test_parity.py` chạy cả 2 bản trên cùng dữ liệu
và so từng con số.

## Cài đặt (5 bước)

1. Tải file **SnakemediaPOD-Chrome.zip** (mục *Artifacts* của lần build mới nhất trên GitHub Actions,
   hoặc mục *Releases*), giải nén ra 1 thư mục cố định, ví dụ `C:\SnakemediaPOD-Chrome`.
   Đừng xoá thư mục này sau khi cài — Chrome đọc tiện ích từ đó.
2. Mở Chrome, gõ `chrome://extensions` vào thanh địa chỉ.
3. Bật **Chế độ dành cho nhà phát triển** (Developer mode) ở góc trên bên phải.
4. Bấm **Tải tiện ích đã giải nén** (Load unpacked) → chọn thư mục ở bước 1 (thư mục có file `manifest.json`).
5. Bấm biểu tượng mảnh ghép 🧩 trên thanh Chrome → ghim **SNAKEMEDIA POD**. Trang bảng điều khiển tự mở lần đầu.

Cập nhật bản mới: giải nén đè vào cùng thư mục, rồi bấm ↻ (Tải lại) trên thẻ tiện ích ở `chrome://extensions`.
Dữ liệu đã quét vẫn giữ nguyên.

## Dùng

- **Đăng nhập Facebook / TikTok** ngay trên Chrome này (tiện ích dùng tài khoản đang đăng nhập).
- Bảng điều khiển: bấm biểu tượng tiện ích → **Mở bảng điều khiển**. Có nút **Xem thử với dữ liệu mẫu**;
  lượt quét thật đầu tiên tự xoá dữ liệu mẫu.
- Khi quét, tiện ích mở **1 cửa sổ Chrome riêng**, cuộn trang rồi tự đóng.
  **Để cửa sổ đó hiện trên màn hình đến khi quét xong** — Chrome ngừng tải trang trong cửa sổ bị thu nhỏ
  hoặc bị cửa sổ khác che hết, khi đó Facebook không tải thêm QC (tiện ích sẽ ghi cảnh báo vào nhật ký).
- Tự quét mỗi đêm chỉ chạy khi Chrome đang mở vào giờ đó.

## An toàn tài khoản

Tiện ích không che giấu việc tự động hoá (không giả dấu vân tay, không giải captcha, không xoay tài khoản);
nó giảm nguy cơ bằng cách quét chậm, giới hạn số lượt và dừng ngay khi bị nghi ngờ.

**Khuyên dùng**: tạo 1 **hồ sơ Chrome riêng** (bấm ảnh hồ sơ góc trên Chrome → Thêm), đăng nhập tài khoản
Facebook/TikTok phụ đã dùng bình thường một thời gian, và cài tiện ích trong hồ sơ đó. Đừng quét bằng tài khoản chính.

Tự động thu thập dữ liệu có thể vi phạm điều khoản của Meta / TikTok. Bạn tự chịu trách nhiệm khi dùng.

## Khác với bản app

| | App (Windows) | Tiện ích Chrome |
|---|---|---|
| Cài | file `.exe` | Load unpacked |
| Trình duyệt quét | Chromium riêng của app | cửa sổ Chrome của bạn |
| Proxy (`proxy.txt`) | có | không (dùng proxy/VPN của máy hoặc tiện ích proxy riêng) |
| Thông báo máy tính | Windows | của Chrome (Windows / macOS / Linux) |
| Tự lưu khi lướt | không | có |
| Dữ liệu nằm ở | `%LOCALAPPDATA%\SnakemediaPOD` | trong hồ sơ Chrome (gỡ tiện ích là mất dữ liệu) |

## Sửa luật / từ khoá

- Ngưỡng chấm nhãn, tốc độ cuộn, giới hạn an toàn mặc định: `lib/config.js`
- Từ khoá loại sản phẩm / niche / cá nhân hoá: `lib/pod.js`

Sửa xong bấm ↻ (Tải lại) ở `chrome://extensions`, rồi vào bảng điều khiển bấm *Chấm lại* (hoặc quét lại).

## Cấu trúc

```
manifest.json        khai báo tiện ích (Manifest V3)
sw.js                phần nền: nhận lệnh, hàng đợi quét, lịch tự quét
lib/                 logic (chuyển từ bản Python): config, db (IndexedDB), fbparser, analyze, landing, pod,
                     social, safety, notify, diag, scanner (điều khiển cửa sổ quét), jobs, api, demo
content/hook.js      chạy trong trang Facebook/TikTok, sao chép phản hồi API dữ liệu (không sửa, không chặn)
content/agent.js     chuyển dữ liệu đó về phần nền
dashboard.*          bảng điều khiển (giao diện giống app)
popup.*              cửa sổ nhỏ khi bấm biểu tượng tiện ích
tests/               kiểm thử bằng Chromium thật trên trang Facebook/TikTok GIẢ
```

## Kiểm thử

```
pip install -r ../snakemedia-pod/requirements.txt
python -m playwright install chromium
cd snakemedia-chrome && python -m pytest -v
```

Đã kiểm thử: so khớp từng con số với bản Python (gom video, nhãn, POD, tuổi trang bán, video viral);
quét trên trang Thư viện QC / TikTok / Creative Center giả; checkpoint; gói chẩn đoán; tự lưu khi lướt;
Telegram giả; mọi màn hình của bảng điều khiển. **Chưa thử trên Facebook / TikTok thật** (môi trường phát triển
bị chặn các trang này) — nếu quét ra 0 kết quả, gửi gói chẩn đoán (.zip) để sửa bộ đọc dữ liệu.
