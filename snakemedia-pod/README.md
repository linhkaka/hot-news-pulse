# SNAKEMEDIA POD 2.0 — soi sản phẩm POD win (bản final)

Tool chạy trên máy tính của bạn (Windows), mở giao diện tiếng Việt trên trình duyệt tại `http://127.0.0.1:8765`.
Muốn dùng ngay trong Chrome, không cần cài: xem bản **tiện ích Chrome** ở `../snakemedia-chrome` (đủ chức năng như app).

**Không có "điểm AI"**: mỗi video được dán nhãn bằng luật đọc được, và màn hình chi tiết ghi rõ ✅/❌ vì sao.

---

## 1. Cài đặt (5 phút)

1. Tải **`SnakemediaPOD-Setup.exe`** ở mục **Releases** của repo (bản `snakepod-v2.0.0`).
2. Bấm đúp để cài. Không cần Python, Chromium có sẵn bên trong, không cần quyền Admin.
   Windows hiện "Windows protected your PC" → bấm **More info → Run anyway** (file chưa ký số).
3. Cuối bước cài, để tick **"Đăng nhập Facebook ngay"** → đăng nhập (nên dùng **tài khoản phụ**) → đóng cửa sổ Chromium.
4. Mở **SNAKEMEDIA POD** từ Desktop / menu Start. Cửa sổ đen là tool đang chạy; đóng nó là tắt tool.

Menu Start → SNAKEMEDIA POD còn có: **Đăng nhập Facebook**, **Đăng nhập TikTok**, **Xem demo**, **Thư mục dữ liệu và proxy**.
Dữ liệu lưu ở `%LOCALAPPDATA%\SnakemediaPOD`. Gỡ cài đặt không xoá dữ liệu; cài bản mới đè lên vẫn giữ dữ liệu.

## 2. Bắt đầu nhanh

1. **Quét từ khoá** → gõ từ khoá (vd `dog mom shirt`) → **Quét**. Hoặc chọn tab **Pinterest / Google Trends / Tự đào**, tick nhiều từ → **Quét các từ đã chọn**.
2. Bảng **tiến độ** bên phải cho biết đang quét việc thứ mấy, đã đọc bao nhiêu QC, còn bao lâu.
3. Xong thì mở **Tổng quan → Video nổi bật**, hoặc các tab **Sắp WIN / Video Win / Tiềm Năng / SP bò sữa**.
4. Bấm **📊 Phân tích** để xem vì sao video có nhãn đó, tuổi thật, các shop đang bán, lịch sử theo ngày.
5. Ưng sản phẩm: **⧉ Clone** vào Shopify (bản nháp), **⬇ Tải video / ảnh**, **Tìm nguồn hàng**, **+ Video test**.

## 3. Sản phẩm "win" được đo thế nào

Sản phẩm win = **video còn mới** + **trang bán mới** + **nhiều shop đang đổ tiền thật**.

| Đo gì | Cách đo |
|---|---|
| Tuổi thật của video | Gom mọi QC dùng chung 1 video (mọi page/shop, **kể cả QC đã tắt**) bằng dấu vân tay ảnh; ảnh hơi khác vẫn gom nếu cùng nội dung chữ / cùng sản phẩm. Tuổi = QC **sớm nhất**. |
| Tuổi trang bán | Shopify: `created_at` của sản phẩm. Nền tảng khác: ngày tạo trong trang → mã UUID v1 → mốc thời gian trong ảnh (2 cách sau là **ước tính**, dấu `*`). |
| Shop đổ tiền | Số shop / page đang chạy, số shop **giữ QC sống 7–14 ngày** (tiêu tiền mà vẫn giữ = có lời). |

| Nhãn / tab | Luật (sửa trong `snakepod/config.py`) | Hợp với |
|---|---|---|
| ⚡ **Sắp WIN** | video ≤ 14 ngày, trang bán không cũ, ≥ 2 shop đang chạy | mọi kênh |
| 🏆 **Video Win** | video ≤ 30 ngày, ≥ 2 shop giữ QC sống 7–14 ngày | Facebook |
| ↗ **Video scale** | 1 shop bơm ≥ 5 QC mới trong 7 ngày | Facebook |
| 🌱 **Video Tiềm Năng** | video ≤ 10 ngày, ≥ 2 QC mới/48h hoặc ≥ 2 page, chưa Sắp WIN | TikTok (bắt sớm) |
| 🐄 **SP bò sữa** | video ≥ 30 ngày, có QC sống ≥ 21 ngày, ≥ 5 QC sống > 14 ngày, ≥ 3 shop | Google Shopping, SEO, sàn |
| ⛔ Trang bán cũ / ⌛ Video già | trang tạo trước video > 14 ngày / QC sớm nhất > 30 ngày | bỏ qua: đến muộn |
| 📈 **QC đang lan nhanh** | ≥ 5 QC mới hoặc ≥ 2 shop mới chép trong 48 giờ | |

POD: tool nhận ra loại sản phẩm (áo, cốc, ornament…), niche (chó, mẹ, y tá…), hàng cá nhân hoá và app POD trên trang bán
(sửa từ khoá trong `snakepod/pod.py`). Mục **🎯 Niche POD** xếp niche theo số video Sắp WIN + Win.

## 4. Các mục trong tool

**Thu thập**
- **🔍 Quét từ khoá**: quét 1 từ, quét hàng loạt (mỗi dòng 1 từ), gợi ý từ khoá 3 tab:
  - **Pinterest**: từ đang tăng trên Pinterest Trends theo nước, kèm % tăng (tool mở trang bằng trình duyệt quét).
  - **Google Trends**: tìm kiếm thịnh hành theo nước (nhiều tin tức / thể thao — tự chọn từ liên quan sản phẩm).
  - **Tự đào**: lấy từ tên sản phẩm / nội dung video hot trong kho mà bạn chưa quét.
  - Mỗi từ ghi đã quét / chưa quét.
- **🏪 Quét store win**: soi các shop đang chạy video hot để tìm sản phẩm khác của họ (Chờ soi / Đã soi, số video mới).
- **⤓ Đào sâu**: soi toàn bộ QC (cả QC đã tắt) của các page đang chạy video Sắp WIN / Tiềm năng → tìm mốc chạy sớm nhất.

**Khám phá** — các tab nhãn ở bảng trên. Mọi danh sách xem được dạng **Danh sách / Lưới / Bảng**, lọc theo loại sản phẩm,
niche, "Chỉ POD", và tải cả trang video / ảnh. Thẻ dạng lưới có vòng tuổi video, tuổi trang bán, "Vì bạn tìm…",
Win / Scale / Shop / Fanpage.

**Bảng chi tiết video** (bấm Phân tích): vì sao có nhãn, sức sống QC (Win / Scale / Cũ), tuổi thật, **lịch sử theo dõi**
14 ngày (+/- so với hôm trước), **đang bán ở N trang** (giá, giá gạch, ngày tạo), **tìm nguồn hàng** (Google Lens,
AliExpress, Amazon, Temu, CJ — tool không nhận hoa hồng), theo dõi shop / page, danh sách QC kèm nút tải từng QC.

**Viral**
- **🔥 Video viral**: TikTok (từ khoá / #hashtag), TikTok thịnh hành, TikTok Top Ads, Facebook Reels (thử nghiệm).
  Nhãn **Đang nổ** (≥ 20.000 xem/giờ, ≤ 3 ngày), **Viral** (≥ 1 triệu xem, ≤ 14 ngày), **Đang lên** (≥ 2.000 xem/giờ, ≤ 7 ngày).
  Từ lần quét thứ 2, tốc độ là **tốc độ thật giữa 2 lần quét**.
- **🌍 Xu hướng thị trường**: hashtag đang lên theo nước (hạng, tăng/giảm, lượt xem, biểu đồ 7 ngày).
- Chỉ 3 nguồn của **TikTok Creative Center** chọn được nước thật sự; TikTok tìm kiếm và Reels ra theo tài khoản + IP của bạn.

**Của tôi**
- **★ Theo dõi đặc biệt** (page / shop), **🧪 Video test**, **🙈 Đã ẩn**.
- **🌙 Tự quét mỗi đêm** (mặc định 1h sáng): quét lại từ khoá đã lưu, page/shop theo dõi, và soi thêm 20 shop. **Tool phải đang mở.**
- **🛡 Chế độ an toàn**, **🔔 Thông báo** (Telegram + Windows), **🛒 Kết nối Shopify** — xem bên dưới.

**Kho**: **🗄 Kho shop**, **🕘 Lịch sử quét**, **⇄ Góp kho dữ liệu** (xuất / nhập file `.json` để gộp kho với đồng đội;
dùng chung được với tiện ích Chrome, QC trùng không bị nhân đôi).

## 5. Kết nối Shopify + nút Clone

1. Mục **🛒 Kết nối Shopify** có hướng dẫn 5 bước: tạo 1 app cho store của bạn trong Shopify Dev Dashboard,
   quyền `write_products,read_products`, cài app vào store, sao chép **Client ID** + **Client secret**.
2. Dán vào tool cùng tên store `ten-store.myshopify.com` → **Kết nối**.
   Store dùng "custom app" kiểu cũ: dán **Admin API access token** (`shpat_…`) vào ô Client secret, để trống Client ID.
3. Bấm **⧉ Clone** trên thẻ video hoặc trên từng trang bán → sản phẩm vào store ở dạng **bản nháp (Draft)**, tag `snakemedia-clone`.

- Trang Shopify: lấy đủ tên, mô tả, ảnh, biến thể, giá, giá gạch. Nền tảng khác: tên, ảnh, giá, mô tả ngắn.
- Client secret chỉ lưu trên máy bạn, không hiện lại trên giao diện, không gửi đi đâu ngoài Shopify.
- **Ảnh / mô tả của shop khác có bản quyền**: sửa lại, làm ảnh riêng; tự đặt giá, tồn kho, vận chuyển rồi mới bật bán.

## 6. Tải ảnh / video

Nút **⬇ Tải video / 🖼 Tải ảnh** trong bảng chi tiết, cho từng QC, và cho cả trang (tối đa 200 video).
File lưu vào `Downloads\SnakemediaPOD\<ngày>` (đổi bằng biến môi trường `SNAKEPOD_MEDIA`).
Link video Facebook **hết hạn sau vài ngày**: tool báo trước giờ hết hạn; hết hạn thì quét lại để lấy link mới.
Chỉ tải để nghiên cứu sản phẩm — đăng lại video của người khác có thể vi phạm bản quyền.

## 7. An toàn tài khoản

Tool **không** che giấu việc tự động hoá (không giả dấu vân tay, không giải captcha, không xoay tài khoản). Nó giảm nguy cơ bằng cách:

- cuộn chậm, nghỉ ngẫu nhiên; nghỉ tối thiểu giữa 2 lượt quét (Facebook 90 giây, TikTok 150, Pinterest 120);
- giới hạn lượt quét mỗi ngày (Facebook 40, TikTok 20, Pinterest 15) — sửa trong **🛡 Chế độ an toàn**;
- **gặp checkpoint / captcha / bắt đăng nhập → dừng ngay** và tạm dừng nền tảng đó. Bấm **Mở trang để xác minh**,
  tự làm theo hướng dẫn, đợi vài tiếng rồi bấm **Đã xử lý, quét tiếp**.

Dùng **tài khoản phụ** đã dùng bình thường một thời gian. Muốn quét qua proxy: mở `proxy.txt`
(menu Start → Thư mục dữ liệu và proxy), điền 1 dòng `http://user:pass@host:port` hoặc `socks5://host:port`,
rồi đăng nhập lại Facebook. Nên dùng proxy dân cư đúng quốc gia đang quét.

**Gói chẩn đoán**: lượt quét ra 0 kết quả / lỗi / checkpoint → tool tự lưu (mã trang, dữ liệu thô, ảnh chụp; email đã che).
Vào **🛡 Chế độ an toàn → Gói chẩn đoán → Tải .zip** và gửi cho người hỗ trợ. Xem trước khi gửi vì có thể chứa tên tài khoản.

## 8. Thông báo

Mục **🔔 Thông báo**: báo khi có video Sắp WIN / Win mới, video TikTok / Reels Đang nổ / Viral mới, page/shop theo dõi lên QC mới.
Telegram: **@BotFather** → `/newbot` → dán token → nhắn `/start` cho bot → **Tự lấy chat ID** → **Gửi thử**.
Token chỉ lưu trên máy bạn và hiện dạng che bớt. Thông báo Windows bật sẵn.

## 9. Nói thẳng: giới hạn

- **Chưa thử trên Facebook / TikTok / Creative Center / Pinterest / Shopify thật** — môi trường phát triển bị chặn các trang này;
  mọi phần quét được kiểm thử trên trang giả dựng trên máy. Lần đầu dùng thật mà ra 0 kết quả: gửi gói chẩn đoán.
- Facebook / TikTok / Pinterest hay đổi giao diện. Bộ đọc dữ liệu đọc "lỏng" nên khá bền, nhưng vẫn có lúc phải sửa.
- Ngày file video được upload lên Facebook: Thư viện QC không có dữ liệu này (tuổi video = QC sớm nhất trên mọi shop).
- Chưa clone được giao diện trang (theme / landing page), chỉ clone sản phẩm. Chưa có kho chung trên máy chủ ("hot toàn hệ thống") — gộp kho bằng file.
- Nhận diện POD / niche dựa trên từ khoá tiếng Anh. Tự quét chỉ chạy khi tool đang mở.

**Pháp lý**: tự động thu thập dữ liệu có thể vi phạm điều khoản của Meta / TikTok / Pinterest, tài khoản quét có thể bị giới hạn.
Quét vừa phải, dùng tài khoản phụ và tự chịu trách nhiệm khi sử dụng.

---

## Cho lập trình viên

Chạy từ mã nguồn trên Windows: cài Python 3.11+ (tick "Add python.exe to PATH") → `CaiDat.bat` → `DangNhapFacebook.bat`
→ `ChayTool.bat` (`ChayDemo.bat` để xem dữ liệu mẫu). Dữ liệu ở `data/`.

```
pip install -r requirements.txt
python -m pytest            # 70 bài kiểm thử (có quét Chromium thật trên trang giả)
python -m snakepod          # chạy máy chủ
```

Đóng gói: GitHub Actions `.github/workflows/snakepod-installer.yml` build mỗi lần đổi code; đẩy tag `snakepod-vX.Y.Z`
để tạo Release kèm file cài và tiện ích Chrome. Logo: `snakepod/static/logo.png` + `packaging/snakepod.ico`.

| File | Việc |
|---|---|
| `scraper.py` | Playwright mở Thư viện QC / TikTok / Creative Center / Pinterest, cuộn, bắt phản hồi dữ liệu |
| `fb_parser.py`, `social.py`, `kwtrends.py` | Đọc QC Facebook; video TikTok / Top Ads / Reels + nhãn viral; xu hướng Pinterest / Google |
| `imagehash.py`, `analyze.py` | dHash thumbnail; gom QC thành video, tính chỉ số, dán nhãn |
| `landing.py`, `pod.py` | Tuổi trang bán; nhận diện POD / niche |
| `shopify.py`, `media.py` | Kết nối Shopify + Clone; tải ảnh / video |
| `jobs.py` | Hàng đợi việc, tiến độ phiên quét, lịch tự quét mỗi đêm |
| `safety.py`, `diag.py`, `notify.py` | Chế độ an toàn; gói chẩn đoán; Telegram / Windows |
| `db.py`, `demo.py` | SQLite; dữ liệu mẫu |
| `server.py`, `static/` | API + giao diện (`static/app.js` dùng chung với tiện ích Chrome qua `snakemedia-chrome/sync_ui.py`) |
