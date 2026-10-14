# WinRadar — soi sản phẩm win từ Thư viện quảng cáo Facebook

Tool chạy trên máy tính của bạn, mở giao diện trên trình duyệt tại `http://127.0.0.1:8765`.
**Không có "điểm AI"**: mỗi video được dán nhãn bằng các luật đọc được, và màn hình chi tiết
ghi rõ ✅/❌ vì sao video có nhãn đó.

## Định nghĩa "win" mà tool dùng

Sản phẩm win = **video còn mới** + **trang bán mới** + **nhiều shop đang đổ tiền thật**.

| Tool đo gì | Cách đo |
|---|---|
| Tuổi thật của video | Gom mọi QC dùng chung 1 video (trên mọi page/shop, **kể cả QC đã tắt**) bằng dấu vân tay ảnh thumbnail. Tuổi = ngày QC **sớm nhất**. Đổi caption, đổi page, lên bài mới đều không giấu được. |
| Tuổi trang bán | Shopify: đọc `created_at` của sản phẩm qua `/products/<handle>.json`. Trang tạo trước video > 14 ngày → tô **đỏ**. |
| Bao nhiêu shop đổ tiền | Đếm số domain/page đang chạy, và số shop **giữ QC sống 7–14 ngày** (đã tiêu tiền mà vẫn giữ = có lời). |
| QC/ngày | Tổng số QC ÷ số ngày từ QC đầu tiên. |

Các nhãn (ngưỡng sửa được trong `winradar/config.py`):

- **Sắp WIN**: video ≤ 14 ngày, trang bán không cũ, ≥ 2 shop đang chạy.
- **Video Win**: video ≤ 30 ngày, ≥ 2 shop giữ QC sống 7–14 ngày.
- **Video scale**: một shop bơm ≥ 5 QC mới trong 7 ngày.
- **Trang bán cũ** / **Video già**: bị loại vì bạn đã đến muộn.
- **Theo dõi**: chưa đủ dữ kiện.

## Cài đặt trên Windows (làm 1 lần)

1. Cài **Python 3.11 trở lên** từ https://www.python.org/downloads/. Khi cài, nhớ **tick "Add python.exe to PATH"**.
2. Tải thư mục `winradar` về máy (trên GitHub bấm **Code → Download ZIP**, rồi giải nén).
3. Bấm đúp **`CaiDat.bat`**, đợi vài phút để cài thư viện và trình duyệt Chromium.
4. Bấm đúp **`DangNhapFacebook.bat`**, đăng nhập Facebook trong cửa sổ hiện ra, rồi **đóng cửa sổ** đó.
   Nên dùng 1 tài khoản Facebook phụ.

## Sử dụng

- **`ChayDemo.bat`**: xem thử giao diện với dữ liệu giả (không quét Facebook).
- **`ChayTool.bat`**: chạy thật. Vào **Quét từ khoá**, gõ từ khoá (vd `garden`, `car gadget`), bấm **Quét**.
  Tool mở Chromium, cuộn Thư viện quảng cáo, rồi tự tải thumbnail, đọc tuổi trang bán và chấm nhãn.
- Bấm vào 1 video để mở bảng chi tiết. Nút **Đào sâu** soi toàn bộ QC (cả QC đã tắt) của các page đang
  chạy video đó, để tìm ra mốc sớm nhất.
- Thanh **Nhật ký** ở dưới: bấm vào để xem tool đang làm gì; nút **Dừng** để dừng việc đang chạy.

Dữ liệu lưu trong thư mục `data/` (SQLite). Xoá thư mục này là làm lại từ đầu.

### Chạy qua proxy (tuỳ chọn)

Mở file **`proxy.txt`**, xoá dấu `#` ở một dòng và điền proxy của bạn, ví dụ:

```
http://user:pass@1.2.3.4:8080
```

Hỗ trợ `http://`, `https://`, `socks5://`. Lần quét sau, Nhật ký sẽ hiện "Dùng proxy …". Nên dùng
proxy dân cư (residential) ở đúng quốc gia đang quét. Khi đổi proxy, chạy lại `DangNhapFacebook.bat`
để Facebook thấy đăng nhập từ IP mới. Đừng đẩy file `proxy.txt` có mật khẩu lên GitHub.

## Giới hạn hiện tại (bản v1)

- Facebook hay đổi giao diện. Tool đọc dữ liệu theo kiểu "tìm mọi object có `ad_archive_id`" nên
  khá bền, nhưng nếu quét ra 0 QC thì cần sửa `winradar/fb_parser.py`.
- Chưa đọc được ngày tạo của trang Shoplazza / nền tảng Trung Quốc (chỉ nhận ra tên nền tảng).
- Chưa có: theo dõi store, tự quét lúc 1h sáng, kho shop, tìm nguồn fulfill.
- Link video của Facebook hết hạn sau vài ngày; khi đó nút "Xem video" mở Thư viện QC thay thế.

## Lưu ý pháp lý

Tự động thu thập dữ liệu từ Facebook có thể vi phạm Điều khoản sử dụng của Meta, và tài khoản dùng
để quét có thể bị giới hạn. Hãy quét với tốc độ vừa phải, dùng tài khoản phụ, và tự chịu trách nhiệm
khi sử dụng.

## Cho lập trình viên

```
pip install -r requirements.txt
python -m pytest            # chạy test
python -m winradar          # chạy server
```

| File | Việc |
|---|---|
| `winradar/scraper.py` | Playwright mở Thư viện QC, cuộn, bắt phản hồi GraphQL |
| `winradar/fb_parser.py` | Rút QC ra từ JSON/HTML của Facebook |
| `winradar/imagehash.py` | dHash thumbnail để nhận ra video trùng |
| `winradar/landing.py` | Đọc tuổi trang bán (Shopify) |
| `winradar/analyze.py` | Gom QC thành video, tính chỉ số, dán nhãn |
| `winradar/jobs.py` | Hàng đợi việc chạy nền + nhật ký |
| `winradar/demo.py` | Tạo dữ liệu giả để xem giao diện |
| `winradar/server.py`, `winradar/static/` | API + giao diện |
