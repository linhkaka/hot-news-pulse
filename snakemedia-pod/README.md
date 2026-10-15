# SNAKEMEDIA POD — soi sản phẩm POD win từ Thư viện quảng cáo Facebook

Tool chạy trên máy tính của bạn, mở giao diện trên trình duyệt tại `http://127.0.0.1:8765`.
**Không có "điểm AI"**: mỗi video được dán nhãn bằng các luật đọc được, và màn hình chi tiết
ghi rõ ✅/❌ vì sao video có nhãn đó.

## Định nghĩa "win" mà tool dùng

Sản phẩm win = **video còn mới** + **trang bán mới** + **nhiều shop đang đổ tiền thật**.

| Tool đo gì | Cách đo |
|---|---|
| Tuổi thật của video | Gom mọi QC dùng chung 1 video (trên mọi page/shop, **kể cả QC đã tắt**) bằng dấu vân tay ảnh thumbnail. Tuổi = ngày QC **sớm nhất**. Đổi caption, đổi page, lên bài mới đều không giấu được. |
| Tuổi trang bán | Shopify: `created_at` qua `/products/<handle>.json`. Nền tảng khác (Shoplazza, Shopline, WooCommerce…): ngày tạo trong dữ liệu sản phẩm nhúng ở trang → mã sản phẩm UUID v1 → mốc thời gian trong link ảnh. Hai cách sau là **ước tính** (dấu `*`). Trang tạo trước video > 14 ngày → tô **đỏ**. |
| Bao nhiêu shop đổ tiền | Đếm số domain/page đang chạy, và số shop **giữ QC sống 7–14 ngày** (đã tiêu tiền mà vẫn giữ = có lời). |
| QC/ngày | Tổng số QC ÷ số ngày từ QC đầu tiên. |

Các nhãn (ngưỡng sửa được trong `snakepod/config.py`):

- **Sắp WIN**: video ≤ 14 ngày, trang bán không cũ, ≥ 2 shop đang chạy.
- **Video Win**: video ≤ 30 ngày, ≥ 2 shop giữ QC sống 7–14 ngày.
- **Video scale**: một shop bơm ≥ 5 QC mới trong 7 ngày.
- **Trang bán cũ** / **Video già**: bị loại vì bạn đã đến muộn.
- **Theo dõi**: chưa đủ dữ kiện.

## Tính năng POD (bản nâng cấp)

- **Nhận diện POD**: loại sản phẩm (Áo, Cốc/Ly, Tranh/Poster, Chăn/Gối, Ornament, Trang trí nhà, Phụ kiện),
  hàng **cá nhân hoá** (personalized, custom name…), app/nền tảng POD trên trang bán (Customily, Teeinblue,
  Printify, Printful, Gearlaunch, Shopbase…). Lọc theo loại sản phẩm / niche / "Chỉ POD" ở mọi danh sách.
- **Niche POD**: bảng niche (chó, mèo, mẹ, y tá, giáo viên, cựu binh, câu cá, Giáng sinh…) xếp theo số video
  Sắp WIN + Win. Thêm/sửa từ khoá niche trong `snakepod/pod.py`.
- **Theo dõi đặc biệt**: bấm `+` cạnh tên shop/page (trong bảng chi tiết video hoặc Kho shop) để theo dõi.
  Xem QC đang chạy, QC mới 24h / 7 ngày, QC vừa tắt.
- **Kho shop**: mọi shop tool từng thấy, nền tảng, số QC, số video Sắp WIN/Win.
- **Tự quét mỗi đêm**: mặc định 1h sáng, quét lại mọi từ khoá đã lưu + mọi page/shop đang theo dõi.
  Đổi giờ hoặc tắt trong mục "Tự quét mỗi đêm". **Tool phải đang mở** lúc đó: khi cài, tick
  "Tự mở SNAKEMEDIA POD khi bật máy", và đặt máy không tự ngủ.

## Cách 1 (dễ nhất): file cài đặt SnakemediaPOD-Setup.exe

1. Tải **`SnakemediaPOD-Setup.exe`** (trong mục **Releases** của repo, hoặc mục **Actions → SNAKEMEDIA POD installer → Artifacts**).
2. Bấm đúp để cài. Không cần cài Python, Chromium có sẵn bên trong, không cần quyền Admin.
   Nếu Windows hiện "Windows protected your PC", bấm **More info → Run anyway** (file chưa ký số).
3. Cuối bước cài, để tick **"Đăng nhập Facebook ngay"**, đăng nhập rồi đóng cửa sổ Chromium.
4. Mở **SNAKEMEDIA POD** từ Desktop hoặc menu Start. Cửa sổ đen là tool đang chạy; đóng nó là tắt tool.

Trong menu Start → SNAKEMEDIA POD còn có: **Đăng nhập Facebook**, **Xem demo**, **Thư mục dữ liệu và proxy**
(chứa `proxy.txt`). Dữ liệu lưu ở `%LOCALAPPDATA%\SnakemediaPOD`, gỡ cài đặt không xoá dữ liệu.

Tự đóng gói (cho lập trình viên): GitHub Actions `.github/workflows/snakepod-installer.yml` tự build
mỗi khi đổi code; đẩy tag `snakepod-v1.0.0` để tạo Release kèm file cài.

## Cách 2: chạy từ mã nguồn trên Windows (làm 1 lần)

1. Cài **Python 3.11 trở lên** từ https://www.python.org/downloads/. Khi cài, nhớ **tick "Add python.exe to PATH"**.
2. Tải thư mục `snakepod` về máy (trên GitHub bấm **Code → Download ZIP**, rồi giải nén).
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

## Giới hạn hiện tại

- Facebook hay đổi giao diện. Tool đọc dữ liệu theo kiểu "tìm mọi object có `ad_archive_id`" nên
  khá bền, nhưng nếu quét ra 0 QC thì cần sửa `snakepod/fb_parser.py`.
- Tuổi trang Shoplazza/nền tảng Trung Quốc là ước tính, và chỉ đọc được khi trang có lộ ngày tạo, mã UUID v1
  hoặc mốc thời gian trong ảnh. Chưa kiểm chứng trên trang Shoplazza thật.
- Nhận diện POD/niche dựa trên từ khoá tiếng Anh, có thể sót hoặc nhầm; sửa bảng từ khoá trong `snakepod/pod.py`.
- Tự quét chỉ chạy khi tool đang mở. Chưa có: tìm nguồn fulfill.
- Link video của Facebook hết hạn sau vài ngày; khi đó nút "Xem video" mở Thư viện QC thay thế.

## Lưu ý pháp lý

Tự động thu thập dữ liệu từ Facebook có thể vi phạm Điều khoản sử dụng của Meta, và tài khoản dùng
để quét có thể bị giới hạn. Hãy quét với tốc độ vừa phải, dùng tài khoản phụ, và tự chịu trách nhiệm
khi sử dụng.

## Cho lập trình viên

```
pip install -r requirements.txt
python -m pytest            # chạy test
python -m snakepod          # chạy server
```

| File | Việc |
|---|---|
| `snakepod/scraper.py` | Playwright mở Thư viện QC, cuộn, bắt phản hồi GraphQL |
| `snakepod/fb_parser.py` | Rút QC ra từ JSON/HTML của Facebook |
| `snakepod/imagehash.py` | dHash thumbnail để nhận ra video trùng |
| `snakepod/landing.py` | Đọc tuổi trang bán (Shopify, UUID, ảnh sản phẩm) |
| `snakepod/pod.py` | Nhận diện loại sản phẩm POD, niche, cá nhân hoá |
| `snakepod/analyze.py` | Gom QC thành video, tính chỉ số, dán nhãn |
| `snakepod/jobs.py` | Hàng đợi việc chạy nền, nhật ký, lịch tự quét mỗi đêm |
| `snakepod/demo.py` | Tạo dữ liệu giả để xem giao diện |
| `snakepod/server.py`, `snakepod/static/` | API + giao diện |
