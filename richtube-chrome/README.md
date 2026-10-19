# RICHTUBE Spy — Tiện ích Chrome (SNAKEMEDIA)

Mổ xẻ video YouTube outlier **ngay trên trình duyệt**. Trên mỗi trang video có nút **🔥 RICHTUBE Spy**,
bấm vào sẽ mở khung bên phải (Side Panel) gồm 3 tab:

1. **Tín hiệu:** điểm TAE, VPH, baseline và biểu đồ sóng **Most Replayed** cùng các đỉnh / vùng trũng có timecode.
2. **Giải mã:** Hook 30 giây đầu, Bao bì (thumbnail + tiêu đề), các nhịp kể chuyện và vũ khí vượt mặt đối thủ lấy từ bình luận.
3. **Sản xuất:** 3 tiêu đề, prompt thumbnail và kịch bản 4 cột, tất cả đều copy 1 chạm. Có thể tải về dạng `.md`.

> Vì sao nên dùng Extension? Tiện ích đọc Heatmap và lời thoại **từ chính trình duyệt của bạn**,
> nên YouTube không chặn như khi đọc từ máy chủ (VPS / Docker).

## Cài đặt (khoảng 2 phút, không cần lập trình)

1. Tải code về máy: vào https://github.com/linhkaka/hot-news-pulse → **Code → Download ZIP** → giải nén.
   Hoặc vào tab **Actions** → chọn lần chạy CI mới nhất → tải file **richtube-chrome.zip** rồi giải nén.
2. Mở Chrome, gõ vào thanh địa chỉ: `chrome://extensions`
3. Bật **Developer mode** (Chế độ dành cho nhà phát triển) ở góc trên bên phải.
4. Bấm **Load unpacked** (Tải tiện ích đã giải nén) → chọn thư mục **`richtube-chrome`**.
5. Trang **Cài đặt** tự mở ra. Nhập:
   - **Gemini API key** (bắt buộc): lấy tại https://aistudio.google.com/apikey. Có thể nhập nhiều key, mỗi key 1 dòng.
   - **YouTube API key** (khuyên dùng): để tính TAE và đọc top bình luận.
6. Ghim tiện ích lên thanh công cụ: bấm biểu tượng 🧩 → 📌 RICHTUBE Spy.

## Sử dụng

- Mở bất kỳ video YouTube nào → bấm **🔥 RICHTUBE Spy** dưới tiêu đề (hoặc bấm biểu tượng tiện ích) → **Spy video này**.
- Mất khoảng 30–90 giây. Kết quả được lưu vào **Lịch sử** (30 video gần nhất) để mở lại không tốn quota.

## Kết nối RICHTUBE Engine (tuỳ chọn)

Trong Cài đặt, nhập **Địa chỉ Engine** (ví dụ `http://localhost:8000` hoặc `http://<IP-VPS>:8000`) và `RICHTUBE_API_KEY` nếu có.
Mỗi lần Spy xong, kết quả sẽ được gửi về Engine để:
- hiện trên **Web Dashboard**,
- tự **đồng bộ Lark Base**,
- **báo Telegram**.

## Lưu ý

- Key chỉ lưu trong máy bạn (`chrome.storage.local`). Tiện ích chỉ gửi dữ liệu tới Google (YouTube/Gemini) và Engine của bạn.
- Không có YouTube API key thì vẫn chạy được, nhưng không có điểm TAE và không đọc được bình luận.
- Video mới hoặc ít view thường chưa có dữ liệu Most Replayed.

## Dành cho lập trình viên

```bash
cd richtube-chrome
npm test     # kiểm thử các thư viện trong lib/ bằng Node (không cần cài gì thêm)
```
