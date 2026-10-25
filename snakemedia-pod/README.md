# SNAKEMEDIA POD — soi sản phẩm POD win từ Thư viện quảng cáo Facebook

Tool chạy trên máy tính của bạn, mở giao diện trên trình duyệt tại `http://127.0.0.1:8765`.
**Không có "điểm AI"**: mỗi video được dán nhãn bằng các luật đọc được, và màn hình chi tiết
ghi rõ ✅/❌ vì sao video có nhãn đó.

## Định nghĩa "win" mà tool dùng

Sản phẩm win = **video còn mới** + **trang bán mới** + **nhiều shop đang đổ tiền thật**.

| Tool đo gì | Cách đo |
|---|---|
| Tuổi thật của video | Gom mọi QC dùng chung 1 video (trên mọi page/shop, **kể cả QC đã tắt**) bằng dấu vân tay ảnh thumbnail; ảnh hơi khác (video bị cắt, thêm chữ) vẫn gom nếu QC cùng nội dung chữ hoặc cùng sản phẩm. Tuổi = ngày QC **sớm nhất**. Đổi caption, đổi page, lên bài mới đều không giấu được. |
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

## Tab theo kênh bán + công cụ đào hàng (bản nâng cấp 2)

- **Nên xem tab nào** (tuỳ kênh bạn giỏi):
  - **Chạy Facebook**: *Video Win* + *Video scale*.
  - **Chạy TikTok**: thêm **Video Tiềm Năng**. Đây là video ≤ 10 ngày, đã có ≥ 2 QC mới trong 48 giờ hoặc ≥ 2 page chạy, nhưng chưa đủ điều kiện Sắp WIN.
  - **Google Shopping / Search, SEO, sàn, free traffic**: **SP bò sữa**. Đây là video ≥ 30 ngày, có QC sống ≥ 21 ngày, ≥ 5 QC sống trên 14 ngày, ≥ 3 shop đang chạy.
  - SP bò sữa xem dạng **bảng**: Ads cũ / Win / Scale / Tuổi video / Tuổi URL / Shop / Fanpage, kèm "+N hôm nay". Mọi danh sách khác cũng chuyển được sang dạng bảng.
- **Lịch sử theo dõi**: mỗi lần chấm lại, tool chụp số fanpage chạy / shop sống / win / scale / số URL của từng video, mỗi ngày 1 dòng. Bảng chi tiết video hiện 14 ngày gần nhất kèm tăng/giảm so với hôm trước.
- **Đang bán ở N trang**: mọi link bán của video, kèm nền tảng, giá, **giá gạch** (compare-at của Shopify) và ngày tạo trang.
- **Quét store win**: soi mọi shop đang chạy video ở các tab Sắp WIN / Win / Scale / Tiềm năng / Bò sữa / Video test / Theo dõi để tìm sản phẩm khác của họ.
  - Danh sách *Chờ soi / Đã soi* (trong 7 ngày), số video mới tìm được sau mỗi lượt soi.
  - Mỗi đêm tự soi thêm N shop (mặc định 20, sửa ở *Tự quét mỗi đêm*).
- **Đào sâu**: danh sách video Sắp WIN / Tiềm năng chưa đào, bấm 1 nút để đào N video đầu danh sách.
  - Đào = soi toàn bộ QC (cả QC đã tắt) của các page đang chạy video, để tìm mốc chạy sớm nhất.
  - Bảng chi tiết ghi rõ "chưa đào" / "đã đào X ngày trước".
- **Quét hàng loạt**: dán nhiều từ khoá (mỗi dòng 1 từ), tool xếp hàng quét lần lượt, có nghỉ an toàn giữa các lượt.
- **Tự đào từ khoá**: gợi ý từ khoá lấy từ tên sản phẩm / nội dung các video đang hot mà bạn chưa quét.
- **Video test** và **Đã ẩn**: đánh dấu video định test; ẩn video không quan tâm khỏi mọi danh sách.
- **Tìm nguồn hàng**: nút tìm theo ảnh (Google Lens) và theo tên sản phẩm (AliExpress, Amazon, Temu, CJ) để hỏi giá xưởng / bên fulfill của bạn. Sửa danh sách trong `SOURCING` của file cấu hình. Tool không nhận hoa hồng từ bên nào.
- **Góp kho dữ liệu**: xuất toàn bộ QC + tuổi trang bán ra 1 file `.json`, đồng đội nhập vào để gộp kho.
  - Mỗi người quét 1 ngách, gộp lại thì đếm được nhiều page/shop chạy cùng 1 video hơn hẳn quét lẻ.
  - File dùng chung được giữa app và tiện ích Chrome.
  - QC trùng không bị nhân đôi.

Chưa làm được (nói thẳng):
- **Ngày file video được upload lên Facebook**: dữ liệu Thư viện QC không có thông tin này. Tuổi video vẫn là "QC sớm nhất, tính cả QC đã tắt, trên mọi shop".
- **Gợi ý từ Pinterest / Google Trends**: chưa làm.
- **Kho chung trên máy chủ**: bản này gộp kho bằng file.

## Clone vào Shopify + gợi ý từ khoá Pinterest / Google + tiến độ quét (bản nâng cấp 4)

- **Thẻ video mới** (Tổng quan → *Video nổi bật*, và kiểu xem *Lưới* ở mọi danh sách):
  - Vòng tròn tuổi video (xanh ≤ 3 ngày, cam ≤ 14 ngày, đỏ già hơn), ngày đăng video và tuổi trang bán.
  - Trang bán cũ hơn video thì ghi đỏ "cũ hơn video N ngày".
  - Dòng "Vì bạn tìm '…'": từ khoá đã quét ra video này.
  - Số Win / Scale / Shop / Fanpage, nút **⧉ Clone** và **📊 Phân tích**.
- **Kết nối Shopify + nút Clone** (mục *Kết nối Shopify*):
  - Tự tạo 1 app cho store của bạn trong Shopify Dev Dashboard (khoảng 5 phút, có hướng dẫn từng bước trong Tool), dán Client ID + Client secret.
  - Store cũ có "custom app": dán Admin API access token (`shpat_…`) vào ô Client secret.
  - Clone tạo sản phẩm **bản nháp (Draft)** gắn tag `snakemedia-clone`: tên, mô tả, ảnh, biến thể, giá, giá gạch. Không tự đăng bán.
  - Trang Shopify lấy được đủ biến thể / ảnh; nền tảng khác chỉ lấy tên, ảnh, giá, mô tả ngắn.
  - Client secret chỉ lưu trên máy bạn (file dữ liệu của tool), không gửi đi đâu ngoài Shopify.
  - **Ảnh / mô tả của shop khác có bản quyền**: sửa lại, làm ảnh riêng trước khi bán.
- **Gợi ý từ khoá** (Quét từ khoá → 3 tab):
  - **Pinterest**: từ khoá đang tăng trên Pinterest Trends theo nước, kèm % tăng và danh mục. Tool mở trang trends.pinterest.com bằng cửa sổ quét (có Chế độ an toàn riêng cho Pinterest).
  - **Google Trends**: tìm kiếm đang thịnh hành theo nước (RSS công khai của Google; nhiều tin tức / thể thao, tự chọn từ liên quan sản phẩm).
  - **Tự đào**: từ tên sản phẩm / nội dung video hot trong kho.
  - Mỗi từ ghi "đã quét / chưa quét". Tick nhiều từ → **Quét các từ đã chọn**.
- **Bảng tiến độ quét** (bên phải trang Quét từ khoá): "Đang quét 3 / 5", việc đang chạy + số QC đã đọc, danh sách việc xong (số QC, thời gian) / đang chờ, tốc độ QC/phút, thời gian còn lại (ước tính) và nút Dừng.

Nói thẳng:
- Shopify, Pinterest Trends, Google Trends **chưa thử với tài khoản / trang thật** (môi trường phát triển bị chặn), chỉ thử với máy chủ giả.
- Tên trường dữ liệu của Pinterest Trends được đọc lỏng; Pinterest có thể bắt đăng nhập (Chế độ an toàn → Đăng nhập Pinterest). Ra 0 từ thì gửi gói chẩn đoán.
- Chưa clone được "trang" (theme / landing page) như SpyWin — chỉ clone sản phẩm.
- "Đang hot toàn hệ thống" (kho chung trên máy chủ) chưa có: kho vẫn gộp bằng file (Góp kho dữ liệu).

## Tải ảnh / video QC + video viral theo thị trường (bản nâng cấp 3)

- **Tải video / ảnh của QC**:
  - Trong bảng chi tiết video có nút **⬇ Tải video** và **🖼 Tải ảnh**. Bảng "các QC" có nút ⬇ / 🖼 cho từng QC.
  - Ở mỗi danh sách có thanh **Tải N video đang xem**: Video / Ảnh / Cả hai (tối đa 200 video mỗi lần).
  - File lưu vào `Downloads\SnakemediaPOD` (đổi bằng biến môi trường `SNAKEPOD_MEDIA`), mỗi ngày 1 thư mục, tên file theo nội dung QC.
  - Video TikTok / Reels: tải ảnh bìa, và tải video nếu trang đó cho phép.
- **Link video của Facebook có hạn dùng** (thường vài ngày).
  - Tool đọc hạn này và báo trước: "link hết hạn lúc …".
  - Link hết hạn thì tải không được; quét lại từ khoá đó để lấy link mới.
  - Ảnh: nếu link gốc hết hạn, tool dùng ảnh đã lưu sẵn trong app.
- **Video viral theo thị trường**:
  - Ô quét Video viral nhận **nhiều từ khoá / #hashtag** (cách nhau dấu phẩy) và cho chọn **nhiều thị trường**: Mỹ, Anh, Canada, Úc, Đức, Pháp, Ý, Tây Ban Nha, Hà Lan, Nhật, Brazil, Mexico, Việt Nam.
  - Nguồn **TikTok thịnh hành** (Creative Center): video đang lên của từng thị trường, có thể lọc thêm theo từ khoá.
  - Lọc danh sách theo thị trường.
- **Xu hướng thị trường** (mục mới): bảng hashtag đang lên của từng nước.
  - Có hạng, tăng/giảm hạng so với lần trước, số bài, lượt xem, biểu đồ 7 ngày.
  - Hashtag khớp từ khoá bạn đang theo dõi được tô màu.
  - Nút **Quét video** (tìm video TikTok của hashtag đó) và **+ Theo dõi**.

Nói thẳng về thị trường:
- Chỉ nguồn của **TikTok Creative Center** (Top Ads, Thịnh hành, Hashtag xu hướng) cho chọn nước thật sự.
- TikTok tìm kiếm thường và Facebook Reels trả kết quả theo **tài khoản + IP** của bạn: muốn xem thị trường khác thì dùng tài khoản / mạng ở nước đó.
- Tên trường dữ liệu của mục Thịnh hành / Hashtag là đọc theo trang hiện tại, **chưa thử trên trang thật** (môi trường phát triển bị chặn). Nếu ra 0 kết quả, gửi gói chẩn đoán.
- Chỉ tải video để nghiên cứu sản phẩm. Đăng lại video của người khác có thể vi phạm bản quyền.

## Chế độ Video viral

Mục **Viral** trên menu:

- **Video viral**: quét theo từ khoá hoặc `#hashtag` trên 3 nguồn:
  - **TikTok (tự nhiên)**: lượt xem, thích, bình luận, chia sẻ, ngày đăng. Cần đăng nhập TikTok 1 lần.
  - **TikTok Top Ads**: quảng cáo hiệu quả nhất trong TikTok Creative Center (lượt thích, CTR, mức ngân sách,
    ngành). Từ khoá có thể bỏ trống để lấy Top Ads chung; chọn khoảng 7/30/180 ngày.
  - **Facebook Reels** (thử nghiệm): video tìm được trên Facebook theo từ khoá. Cấu trúc dữ liệu của Facebook
    hay đổi nên phần này dễ hỏng nhất.
- Nhãn (ngưỡng trong `snakepod/config.py`):
  - **Đang nổ**: ≥ 20.000 lượt xem/giờ và video ≤ 3 ngày tuổi.
  - **Viral**: ≥ 1 triệu lượt xem và video ≤ 14 ngày tuổi.
  - **Đang lên**: ≥ 2.000 lượt xem/giờ và video ≤ 7 ngày tuổi.
  - Lượt xem/giờ lấy **tốc độ thật giữa 2 lần quét gần nhất** (từ lần quét thứ 2), nếu chưa có thì lấy trung
    bình từ lúc đăng. Tick "Tự quét mỗi đêm" để tool tự cập nhật số liệu mỗi đêm.
- **QC đang lan nhanh**: video QC Facebook có ≥ 5 QC mới hoặc ≥ 2 shop mới chép trong 48 giờ qua.

Đăng nhập TikTok: menu Start → **Đăng nhập TikTok** (hoặc `DangNhapTikTok.bat` khi chạy từ mã nguồn).

## Chế độ an toàn (tránh checkpoint)

Tool **không** che giấu việc tự động hoá (không giả dấu vân tay trình duyệt, không tự giải captcha, không xoay
vòng tài khoản). Nó giảm nguy cơ bị checkpoint bằng cách cư xử như người dùng bình thường:

- Cuộn trang chậm, nghỉ ngẫu nhiên 2,5–5,5 giây giữa các lần cuộn; đào sâu nhiều page thì nghỉ 20–45 giây giữa 2 page.
- Nghỉ tối thiểu giữa 2 lượt quét cùng nền tảng (mặc định Facebook 90 giây, TikTok 150 giây).
- Giới hạn số lượt quét mỗi ngày (mặc định Facebook 40, TikTok 20). Sửa trong mục **🛡 Chế độ an toàn**.
- **Gặp checkpoint, captcha hoặc trang bắt đăng nhập lại → dừng ngay** và tạm dừng mọi lượt quét của nền tảng đó
  (kể cả lượt tự quét ban đêm). Màn hình hiện băng cảnh báo đỏ: bấm **Mở trình duyệt để xác minh**, tự làm theo
  hướng dẫn của Facebook/TikTok, đóng cửa sổ, đợi vài tiếng rồi bấm **Đã xử lý, quét tiếp**.

## Thông báo (Telegram / Windows)

Mục **🔔 Thông báo**: tool báo khi có video Sắp WIN / Win mới, video TikTok/Reels Đang nổ / Viral mới, hoặc
page/shop đang theo dõi lên QC mới. Mỗi video chỉ báo 1 lần; video có từ trước khi bật sẽ không bị báo.

Cài Telegram: mở **@BotFather** → `/newbot` → nhận token → dán vào tool → nhắn `/start` cho bot →
bấm **Tự lấy chat ID** → **Gửi thử**. Thông báo Windows bật sẵn (Windows 10/11, không cần cài thêm).

## Gói chẩn đoán

Khi 1 lượt quét ra 0 kết quả, lỗi hoặc gặp checkpoint, tool tự lưu **gói chẩn đoán** (mã trang, dữ liệu thô,
ảnh chụp màn hình; email đã được che). Vào **🛡 Chế độ an toàn → Gói chẩn đoán**, bấm **Tải .zip** và gửi
cho người hỗ trợ để sửa nhanh. Trang có thể chứa tên tài khoản của bạn, nên xem trước khi gửi.

## Đổi logo

Logo nằm ở `snakepod/static/logo.png` (giao diện, ảnh vuông PNG) và `packaging/snakepod.ico` (biểu tượng file .exe và bộ cài).
Thay 2 file này bằng logo của bạn (giữ nguyên tên file) rồi đóng gói lại.

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
- Phần TikTok, Top Ads và Facebook Reels mới chỉ được thử trên trang giả dựng trên máy (môi trường phát triển bị
  chặn các trang này). TikTok chặn máy tự động khá gắt: nên đăng nhập, quét chậm, dùng proxy dân cư nếu bị chặn.
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
| `snakepod/social.py` | Đọc video TikTok / Top Ads / Reels và chấm nhãn viral |
| `snakepod/analyze.py` | Gom QC thành video, tính chỉ số, dán nhãn |
| `snakepod/jobs.py` | Hàng đợi việc chạy nền, nhật ký, lịch tự quét mỗi đêm, tải ảnh/đọc trang bán song song |
| `snakepod/notify.py` | Thông báo Telegram / Windows |
| `snakepod/diag.py` | Gói chẩn đoán khi quét lỗi |
| `snakepod/safety.py` | Chế độ an toàn: phát hiện checkpoint, giới hạn quét |
| `snakepod/demo.py` | Tạo dữ liệu giả để xem giao diện |
| `snakepod/server.py`, `snakepod/static/` | API + giao diện |
