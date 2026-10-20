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

## Tải ảnh / video QC + video viral theo thị trường (bản nâng cấp 3)

- **Tải video / ảnh của QC**:
  - Trong bảng chi tiết video có nút **⬇ Tải video** và **🖼 Tải ảnh**. Bảng "các QC" có nút ⬇ / 🖼 cho từng QC.
  - Ở mỗi danh sách có thanh **Tải N video đang xem**: Video / Ảnh / Cả hai (tối đa 200 video mỗi lần).
  - File lưu vào thư mục Tải xuống của Chrome, mục `SnakemediaPOD`, mỗi ngày 1 thư mục, tên file theo nội dung QC.
  - Video TikTok / Reels: tải ảnh bìa, và tải video nếu trang đó cho phép.
- **Link video của Facebook có hạn dùng** (thường vài ngày).
  - Tool đọc hạn này và báo trước: "link hết hạn lúc …".
  - Link hết hạn thì tải không được; quét lại từ khoá đó để lấy link mới.
  - Ảnh: nếu link gốc hết hạn, tool dùng ảnh đã lưu sẵn trong tiện ích.
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
dashboard.*          bảng điều khiển — dashboard.js / style.css là bản sao giao diện của app
                     (sửa ở snakemedia-pod/snakepod/static rồi chạy: python snakemedia-chrome/sync_ui.py)
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
