// Mọi ngưỡng chấm điểm nằm ở đây (giống snakemedia-pod/snakepod/config.py). Không có "điểm AI".
export const C = {
  // Quét
  DEFAULT_COUNTRY: "US",
  DEFAULT_MAX_ADS: 300,          // số QC tối đa mỗi lượt quét từ khoá
  DIG_MAX_PAGES: 6,              // đào sâu: số page tối đa soi cho 1 video
  DIG_MAX_ADS_PER_PAGE: 150,

  // Chế độ an toàn: cuộn chậm như người thật (mili giây nghỉ giữa 2 lần cuộn, ngẫu nhiên trong khoảng)
  SCROLL_PAUSE_MS: [2500, 5500],
  MAX_SCROLL_ROUNDS: 60,         // tối đa số lần cuộn mỗi trang
  LOAD_WAIT_MS: 4000,            // chờ sau khi trang tải xong rồi mới đọc
  PREPARE_WAIT_MS: 3000,         // chờ sau khi gõ từ khoá (Top Ads)
  PAGE_GAP_S: [20, 45],          // đào sâu nhiều page: nghỉ ngẫu nhiên giữa 2 page (giây)
  SAFETY_DEFAULT_LIMITS: {
    facebook: {min_gap_s: 90, max_per_day: 40},
    tiktok: {min_gap_s: 150, max_per_day: 20},
  },

  AUTO_SCAN_HOUR: 1,             // giờ tự quét mỗi đêm (giờ máy tính), sửa được trên giao diện
  HTTP_WORKERS: 8,               // số ảnh / trang bán tải cùng lúc (không đụng Facebook/TikTok)
  PASSIVE_DELAY_S: 20,           // tự lưu khi lướt: chờ bạn lướt xong N giây rồi mới xử lý

  // Gom QC cùng 1 video: 2 ảnh thumbnail khác nhau <= N bit (dHash 64 bit) coi như cùng video
  DHASH_MAX_DISTANCE: 6,
  // Ảnh hơi khác hơn (video bị cắt, thêm chữ) vẫn gom nếu QC có cùng nội dung chữ hoặc cùng sản phẩm
  DHASH_LOOSE_DISTANCE: 12,

  // Luật chấm nhãn (đơn vị: ngày)
  SCALE_MAX_DAYS: 7,             // QC đang chạy < 7 ngày  -> "Scale" (mới lên)
  WIN_MAX_DAYS: 14,              // QC sống 7-14 ngày      -> "Win" (đã có người đổ tiền và giữ)
  NEW_VIDEO_DAYS: 14,            // video <= 14 ngày tuổi  -> còn mới
  OLD_VIDEO_DAYS: 30,            // video > 30 ngày tuổi   -> già, đi muộn
  PAGE_OLDER_THAN_VIDEO: 14,     // trang bán tạo trước video > 14 ngày -> tô đỏ
  MIN_SHOPS_SAP_WIN: 2,          // ít nhất 2 shop (domain) khác nhau đang chạy
  MIN_SHOPS_WIN: 2,              // ít nhất 2 shop giữ QC sống 7-14 ngày
  MIN_SCALE_ADS: 5,              // 1 shop bơm >= 5 QC mới trong 7 ngày -> "Video scale"
  NEW_POST_DAYS: 3,              // shop có QC bắt đầu trong 3 ngày -> "đang lên bài mới"

  // QC Facebook "đang lan nhanh": nhiều QC / shop mới chép video trong 48 giờ qua
  SPREAD_HOURS: 48,
  SPREAD_MIN_NEW_ADS: 5,
  SPREAD_MIN_NEW_SHOPS: 2,

  // Video viral (TikTok / Facebook Reels). vph = lượt xem mỗi giờ
  VIRAL_EXPLODE_VPH: 20000,      // "Đang nổ": >= 20.000 lượt xem/giờ ...
  VIRAL_EXPLODE_MAX_DAYS: 3,     // ... và video <= 3 ngày tuổi
  VIRAL_MIN_VIEWS: 1000000,      // "Viral": >= 1 triệu lượt xem ...
  VIRAL_MAX_DAYS: 14,            // ... và video <= 14 ngày tuổi
  VIRAL_RISING_VPH: 2000,        // "Đang lên": >= 2.000 lượt xem/giờ ...
  VIRAL_RISING_MAX_DAYS: 7,      // ... và video <= 7 ngày tuổi

  // Video Tiềm Năng: vừa nhú, shop bắt đầu nhảy vào nhưng chưa chín (chưa đủ điều kiện Sắp WIN / Win)
  POTENTIAL_MAX_DAYS: 10,        // video <= 10 ngày tuổi ...
  POTENTIAL_MIN_NEW_ADS: 2,      // ... và >= 2 QC mới trong 48 giờ
  POTENTIAL_MIN_PAGES: 2,        // ... hoặc >= 2 page đang chạy

  // SP bò sữa: chạy đều nhiều tuần, không bùng lên rồi tắt (hợp Google Shopping / SEO / sàn / free traffic)
  COW_MIN_DAYS: 30,              // video >= 30 ngày tuổi
  COW_MIN_RUN_DAYS: 21,          // có QC đang chạy liên tục >= 21 ngày
  COW_MIN_OLD_ADS: 5,            // >= 5 QC đang chạy đã sống > 14 ngày
  COW_MIN_SHOPS: 3,              // >= 3 shop đang chạy

  DIG_FRESH_DAYS: 7,             // video đã đào trong 7 ngày -> không cần đào lại
  STORE_FRESH_DAYS: 7,           // shop đã soi trong 7 ngày -> "Đã soi"
  AUTO_SWEEP_STORES: 20,         // mỗi đêm soi thêm 20 shop đang chạy video hot (sửa được trên giao diện)
  HISTORY_DAYS: 14,              // lịch sử theo dõi mỗi video: giữ 14 ngày gần nhất trên giao diện

  // Tìm nguồn hàng: {q} = tên sản phẩm, {image} = link ảnh. Thêm/bớt tuỳ ý.
  SOURCING: [
    ["Google Lens (theo ảnh)", "https://lens.google.com/uploadbyurl?url={image}"],
    ["AliExpress", "https://www.aliexpress.com/wholesale?SearchText={q}"],
    ["Amazon", "https://www.amazon.com/s?k={q}"],
    ["Temu", "https://www.temu.com/search_result.html?search_key={q}"],
    ["CJdropshipping", "https://www.google.com/search?q=site%3Acjdropshipping.com+{q}"],
  ],

  MEDIA_BATCH_MAX: 200,          // tối đa số video mỗi lần tải hàng loạt (lưu vào Tải về/SnakemediaPOD)
  // Thị trường cho video viral. Nguồn chọn được thị trường: TikTok Top Ads, TikTok thịnh hành / hashtag xu hướng
  // của Creative Center. TikTok tìm kiếm thường và Facebook Reels ra kết quả theo tài khoản + IP của bạn.
  MARKETS: {US: "Mỹ", GB: "Anh", CA: "Canada", AU: "Úc", DE: "Đức", FR: "Pháp", IT: "Ý", ES: "Tây Ban Nha",
    NL: "Hà Lan", JP: "Nhật", BR: "Brazil", MX: "Mexico", VN: "Việt Nam"},
};

// Địa chỉ các trang được quét. Bài kiểm thử đổi sang trang giả trên máy (xem applyDev).
export const URLS = {
  FB: "https://www.facebook.com",
  TIKTOK: "https://www.tiktok.com",
  CREATIVE_CENTER: "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en",
  TREND_VIDEOS: "https://ads.tiktok.com/business/creativecenter/inspiration/popular/video/pc/en",
  TREND_TAGS: "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
  TG_API: "https://api.telegram.org",
};

// Trang được gắn bộ bắt dữ liệu (content script)
export const CAPTURE_MATCHES = [
  "https://www.facebook.com/ads/library*",
  "https://www.facebook.com/search/*",
  "https://www.tiktok.com/*",
  "https://ads.tiktok.com/business/creativecenter/*",
];
export const DEV = {matches: []};

// Chỉ dùng cho bài kiểm thử: {config: {...}, urls: {...}, matches: ["http://127.0.0.1/*"]}
export function applyDev(dev) {
  if (!dev) return;
  Object.assign(C, dev.config || {});
  Object.assign(URLS, dev.urls || {});
  DEV.matches = dev.matches || [];
}
