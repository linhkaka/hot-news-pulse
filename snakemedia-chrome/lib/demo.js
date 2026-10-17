// Dữ liệu GIẢ để xem thử giao diện mà không cần quét (giống snakepod/demo.py).
// Chỉ tạo khi tiện ích chưa có dữ liệu thật; lần quét thật đầu tiên tự xoá dữ liệu mẫu.
import * as db from "./db.js";
import {buildVideos} from "./analyze.js";
import {dhashBitmap, smallJpeg} from "./imagehash.js";

const DAY = 86400;
const DATA_STORES = ["ads", "landings", "videos", "follows", "watch_keywords", "social_videos", "social_snapshots",
  "social_watch", "notified", "scans", "thumbs", "rate_events", "diag"];

const PRODUCTS = [
  // [nội dung, giá, ngày tuổi video, ngày tuổi trang bán, [[shop, số page, [tuổi QC đang chạy]]], số QC đã tắt]
  ["Personalized Dog Mom Shirt 🐶 Custom name tee for every dog lover", "14.99", 6, 6,
    [["bloomyard.com", 3, [5, 4, 2]], ["gardenjoy.shop", 2, [6, 1]]], 2],
  ["Funny Nurse Coffee Mug ☕ The gift every night-shift nurse needs", "26.00", 12, 11,
    [["skyflyer.co", 4, [11, 9, 8, 3]], ["kidzone-us.com", 3, [10, 7, 2]], ["toyrush.store", 1, [4]]], 5],
  ["Custom Family Christmas Ornament 🎄 Add your names", "27.99", 14, 15,
    [["autoneat.com", 3, [13, 8, 1]], ["drivepro.shop", 2, [9, 3]]], 4],
  ["Halloween Witch Doormat 🧹 Spooky season is here", "22.99", 9, 40,
    [["xmasglow.com", 4, [8, 6, 3, 1]], ["festivehome.co", 2, [5, 2]]], 1],
  ["Fishing Grandpa Hoodie 🎣 Reel cool papa", "19.99", 48, 50,
    [["edcgear.com", 3, [40, 20, 3]], ["pocketpro.shop", 2, [30, 15]]], 12],
  ["In Loving Memory Canvas 🕊 Personalized memorial wall art", "29.99", 4, 4,
    [["advent-cozy.com", 6, [4, 3, 2, 1, 1, 0]], ["memorialgift.co", 2, [1, 0]]], 0],
  ["Veteran Truck Flag 🇺🇸 Proud army veteran", "34.99", 3, null,
    [["moto-loud.com", 2, [3, 2]]], 0],
];

const SOCIAL = [
  // [nền tảng, id, caption, tác giả, giờ tuổi, [lượt xem theo 2 lần quét cách 6 giờ], thích, bình luận, chia sẻ, extra]
  ["tiktok", "7301", "POV: you ordered the personalized dog mom hoodie 🐶 #dogmom #customgift", "pawsandprints",
    30, [600000, 1100000], 140000, 2100, 9800, null],
  ["tiktok", "7302", "Nurse tumbler that survives a 12h shift ☕ #nurse #nurselife", "nightshiftnina",
    120, [2300000, 2380000], 310000, 4200, 21000, null],
  ["tiktok", "7303", "Custom family christmas ornament unboxing 🎄 add your names", "cozyhomefinds",
    70, [180000, 260000], 22000, 340, 1200, null],
  ["tiktok", "7304", "Fishing grandpa shirt restock 🎣", "reelcoolpapa", 600, [90000, 90400], 4000, 50, 90, null],
  ["tiktok_ads", "ad9001", "Personalized pet portrait canvas - turn your dog into art", "PawCanvas", null, [null],
    54000, 800, 1900, {brand_name: "PawCanvas", ctr: "Top 5%", cost: 3, industry_key: "Home Decor"}],
  ["tiktok_ads", "ad9002", "Teacher appreciation mug they will actually use", "MugMuse", null, [null],
    12000, 150, 400, {brand_name: "MugMuse", ctr: "Top 20%", cost: 2, industry_key: "Gifts"}],
  ["fb_reels", "r501", "Memorial canvas made her cry 😭 personalized in loving memory", "Forever Prints",
    40, [350000, 520000], 18000, 2400, 6100, null],
];

function rng(seed) {   // mulberry32
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

async function image(seed) {
  const r = rng(seed + 1), int = (a, b) => a + Math.floor(r() * (b - a + 1));
  const c = new OffscreenCanvas(320, 320);
  const ctx = c.getContext("2d");
  ctx.fillStyle = `rgb(${int(40, 220)},${int(40, 220)},${int(40, 220)})`;
  ctx.fillRect(0, 0, 320, 320);
  for (let i = 0; i < 6; i++) {
    const x = int(0, 260), y = int(0, 260), w = int(40, 120), h = int(40, 120);
    ctx.fillStyle = `rgb(${int(0, 255)},${int(0, 255)},${int(0, 255)})`;
    ctx.beginPath();
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  return [dhashBitmap(c), await smallJpeg(c)];
}

const title = s => s.replace(/[A-Za-z]+/g, w => w[0].toUpperCase() + w.slice(1).toLowerCase());

export async function hasRealData() {
  const ads = await db.allAds(), soc = await db.socialRows();
  return ads.some(a => !a.ad_id.startsWith("demo")) || soc.some(v => v.keyword !== "demo");
}

async function wipeData() {
  for (const s of DATA_STORES) await db.clear(s);
}

// Lần quét thật đầu tiên: xoá dữ liệu mẫu để không lẫn với dữ liệu thật.
export async function clearIfDemo(log = () => {}) {
  if (!(await db.getSetting("demo", false))) return;
  await wipeData();
  await db.setSetting("demo", false);
  log("Đã xoá dữ liệu mẫu trước lượt quét thật đầu tiên");
}

export async function load() {
  if (await hasRealData()) throw new Error("Tiện ích đã có dữ liệu thật, không tạo dữ liệu mẫu.");
  await wipeData();
  const now = db.now();
  const ads = [];
  let n = 0;
  for (let pi = 0; pi < PRODUCTS.length; pi++) {
    const [text, price, vage, lage, shops, gone] = PRODUCTS[pi];
    const [h, jpg] = await image(pi);
    const thumb = `demo_p${pi}.jpg`;
    await db.saveThumb(thumb, jpg);
    for (let si = 0; si < shops.length; si++) {
      const [shop, pages, runs] = shops[si];
      const link = `https://${shop}/products/demo-${pi}`;
      await db.saveLanding({url: link, final_url: link, domain: shop, platform: "shopify",
        created_ts: lage ? now - lage * DAY : null, published_ts: null, title: text, price, checked_ts: now,
        error: null, date_source: lage ? "api" : null});
      const all = runs.map(r => [r, true]);
      if (si === 0) for (let k = 0; k < gone; k++) all.push([vage - k % 3, false]);
      all[0] = [si === 0 ? Math.max(all[0][0], vage) : all[0][0], true];
      all.forEach(([age, active], k) => {
        n++;
        ads.push({ad_id: `demo${n}`, collation_id: null, collation_count: 1, page_id: `${pi}${si}${k % pages}`,
          page_name: `${title(shop.split(".")[0])} ${k % pages + 1}`, start_ts: now - age * DAY,
          end_ts: active ? null : now - DAY, is_active: active ? 1 : 0, title: null, body: text, link_url: link,
          domain: shop, thumb_url: null, video_url: null, _thumb: thumb, _hash: h});
      });
    }
  }
  await db.upsertAds(ads, "demo");
  for (const a of ads) await db.setThumb(a.ad_id, a._thumb, a._hash);
  await db.replaceVideos(buildVideos(await db.allAds(), await db.landingsByUrl()));

  for (let i = 0; i < SOCIAL.length; i++) {
    const [plat, itemId, cap, author, ageH, views, likes, comments, shares, extra] = SOCIAL[i];
    const [, jpg] = await image(100 + i);
    const name = `s_demo_${itemId}.jpg`;
    await db.saveThumb(name, jpg);
    const base = {vid: `${plat}:${itemId}`, platform: plat, item_id: itemId,
      url: plat !== "fb_reels" ? "https://www.tiktok.com/" : "https://www.facebook.com/reel/",
      author, caption: cap, cover_url: null, video_url: null, saves: null,
      created_ts: ageH ? now - ageH * 3600 : null, duration: 20, extra: extra ? JSON.stringify(extra) : null,
      likes, comments, shares};
    for (let k = 0; k < views.length; k++)
      await db.upsertSocial([{...base, views: views[k]}], "demo", now - (views.length - 1 - k) * 6 * 3600);
    await db.setSocialCover(base.vid, name);
  }
  await db.addSocialWatch("tiktok", "dog mom shirt", "US");
  await db.addSocialWatch("tiktok_ads", "", "US");
  await db.addWatchKeyword("dog mom shirt", "US");
  await db.addWatchKeyword("personalized ornament", "US");
  await db.addFollow("shop", "bloomyard.com", "bloomyard.com");
  await db.addFollow("page", "100", "Bloomyard 1");
  await db.setSetting("demo", true);
  return ads.length;
}
