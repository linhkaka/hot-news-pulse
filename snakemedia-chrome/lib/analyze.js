// Gom QC thành "video" rồi chấm nhãn bằng luật rõ ràng (giống snakepod/analyze.py, ngưỡng ở config.js).
//
// Một "video" = nhóm QC dùng chung 1 nội dung, trên mọi page/shop, cả QC đang chạy lẫn đã tắt.
// Tuổi video = ngày QC SỚM NHẤT trong nhóm, nên shop có đổi caption/đổi page/lên bài mới
// thì cũng không giấu được tuổi thật.
import {C} from "./config.js";
import {POD_PLATFORMS, classify} from "./pod.js";
import {popcount} from "./imagehash.js";
import {urlparse} from "./fbparser.js";

const DAY = 86400;
const now = () => Math.floor(Date.now() / 1000);

class UnionFind {
  constructor() { this.parent = new Map(); }
  find(x) {
    if (!this.parent.has(x)) this.parent.set(x, x);
    while (this.parent.get(x) !== x) {
      this.parent.set(x, this.parent.get(this.parent.get(x)));
      x = this.parent.get(x);
    }
    return x;
  }
  union(a, b) {
    const ra = this.find(a), rb = this.find(b);
    if (ra !== rb) {
      const [lo, hi] = ra < rb ? [ra, rb] : [rb, ra];
      this.parent.set(hi, lo);
    }
  }
}

// 12 chữ đầu của nội dung QC (bỏ emoji, dấu câu). Quá ngắn thì không dùng.
export function textKey(body) {
  const words = (body || "").toLowerCase().match(/[a-z0-9]+/g) || [];
  return words.length >= 4 ? words.slice(0, 12).join(" ") : null;
}

// Tên sản phẩm trong link trang bán: .../products/personalized-dog-mom-shirt -> 'personalized-dog-mom-shirt'.
// Tên quá chung chung (ngắn, ít gạch nối) thì bỏ qua để không gom nhầm.
export function productKey(linkUrl) {
  if (!linkUrl) return null;
  const m = /\/products?\/([^/?#]+)/.exec(urlparse(linkUrl).path);
  if (!m) return null;
  const handle = m[1].toLowerCase().replace(/-\d+$/, "");
  return handle.length >= 10 && (handle.match(/-/g) || []).length >= 2 ? handle : null;
}

// Làm tròn như Python round(): nửa về số chẵn
function pyRound(x, nd = 0) {
  const k = 10 ** nd, y = x * k, r = Math.round(y);
  return (Math.abs(y % 1) === 0.5 ? 2 * Math.round(y / 2) : r) / k;
}

// Các cặp [i, j] có khoảng cách bit <= maxDistance, không cần so mọi cặp.
// Chia 64 bit thành maxDistance+1 khúc: 2 hash lệch <= maxDistance bit chắc chắn trùng nguyên 1 khúc
// (nguyên lý chuồng bồ câu), nên chỉ cần so các hash cùng khúc.
export function nearPairs(hashes, maxDistance) {
  const n = maxDistance + 1;
  const bounds = Array.from({length: n + 1}, (_, k) => pyRound(64 * k / n));
  const buckets = new Map();
  hashes.forEach((h, idx) => {
    for (let c = 0; c < n; c++) {
      const lo = BigInt(bounds[c]), width = BigInt(bounds[c + 1] - bounds[c]);
      const key = c + ":" + ((h >> lo) & ((1n << width) - 1n)).toString(16);
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(idx);
    }
  });
  const seen = new Set(), out = [];
  for (const members of buckets.values()) {
    for (let a = 0; a < members.length; a++) for (let b = a + 1; b < members.length; b++) {
      const i = members[a], j = members[b], k = i + "," + j;
      if (!seen.has(k) && popcount(hashes[i] ^ hashes[j]) <= maxDistance) { seen.add(k); out.push([i, j]); }
    }
  }
  return out;
}

// Trả về Map {cid: [ad, ...]}. Gom QC cùng 1 video theo:
//   1. cùng collation của Facebook;
//   2. ảnh thumbnail gần giống (<= maxDistance bit);
//   3. ảnh hơi khác (<= looseDistance bit, vd video bị cắt/thêm chữ) NHƯNG cùng nội dung chữ hoặc cùng sản phẩm.
export function cluster(ads, maxDistance = C.DHASH_MAX_DISTANCE, looseDistance = C.DHASH_LOOSE_DISTANCE) {
  const uf = new UnionFind();
  const byKey = new Map();
  const add = (k, id) => { if (!byKey.has(k)) byKey.set(k, []); byKey.get(k).push(id); };
  for (const a of ads) {
    uf.find(a.ad_id);
    if (a.collation_id) add("c:" + a.collation_id, a.ad_id);
    if (a.dhash) add("h:" + a.dhash, a.ad_id);
  }
  for (const ids of byKey.values()) for (const other of ids.slice(1)) uf.union(ids[0], other);

  const hashes = [...new Set(ads.filter(a => a.dhash).map(a => a.dhash))].sort();
  const ints = hashes.map(h => BigInt("0x" + h));
  for (const [i, j] of nearPairs(ints, maxDistance)) uf.union(byKey.get("h:" + hashes[i])[0], byKey.get("h:" + hashes[j])[0]);

  // Mức lỏng: chỉ so các ảnh có chung nội dung chữ hoặc chung sản phẩm (nhóm nhỏ -> so từng cặp được)
  const byHint = new Map();
  for (const a of ads) {
    if (!a.dhash) continue;
    for (const hint of [textKey(a.body), productKey(a.link_url)]) {
      if (!hint) continue;
      if (!byHint.has(hint)) byHint.set(hint, new Set());
      byHint.get(hint).add(a.dhash);
    }
  }
  for (const set of byHint.values()) {
    const members = [...set].sort().slice(0, 300);
    const big = members.map(h => BigInt("0x" + h));
    for (let x = 0; x < members.length; x++) for (let y = x + 1; y < members.length; y++)
      if (popcount(big[x] ^ big[y]) <= looseDistance)
        uf.union(byKey.get("h:" + members[x])[0], byKey.get("h:" + members[y])[0]);
  }

  const groups = new Map();
  for (const a of ads) {
    const r = uf.find(a.ad_id);
    if (!groups.has(r)) groups.set(r, []);
    groups.get(r).push(a);
  }
  return groups;
}

const daysOf = (ts, t) => (ts ? (t - ts) / DAY : null);
const w = a => a.collation_count || 1;
const sum = xs => xs.reduce((s, x) => s + x, 0);
const cmpTuple = (x, y) => { for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] > y[i] ? 1 : -1; return 0; };
const cut = (s, n) => Array.from(s).slice(0, n).join("");
const sortedStr = xs => [...xs].sort();

export function summarize(cid, ads, landings, t = null) {
  t = t || now();
  const starts = ads.map(a => a.start_ts).filter(Boolean);
  const firstTs = starts.length ? Math.min(...starts) : null;
  const videoAge = daysOf(firstTs, t);

  const active = ads.filter(a => a.is_active);
  const inactive = ads.filter(a => !a.is_active);

  const buckets = {scale: 0, win: 0, old: 0};
  const shopRun = new Map();   // domain -> số ngày chạy của các QC đang sống
  for (const a of active) {
    const run = daysOf(a.start_ts, t) || 0;
    const key = run < C.SCALE_MAX_DAYS ? "scale" : run <= C.WIN_MAX_DAYS ? "win" : "old";
    buckets[key] += w(a);
    const d = a.domain || "?";
    if (!shopRun.has(d)) shopRun.set(d, []);
    shopRun.get(d).push(run);
  }

  const pagesAll = new Set(ads.filter(a => a.page_id).map(a => a.page_id));
  const pagesActive = new Set(active.filter(a => a.page_id).map(a => a.page_id));
  const shopsAll = new Set(ads.filter(a => a.domain).map(a => a.domain));
  const shopsActive = new Set(active.filter(a => a.domain).map(a => a.domain));
  const shopsWin = [...shopRun].filter(([d, runs]) => d !== "?" && runs.some(r => C.SCALE_MAX_DAYS <= r && r <= C.WIN_MAX_DAYS));
  const shopsNewPost = [...shopRun].filter(([d, runs]) => d !== "?" && Math.min(...runs) < C.NEW_POST_DAYS);
  const adsTotal = sum(ads.map(w));

  // Độ lan: QC / shop / page MỚI chép video trong SPREAD_HOURS giờ qua
  const recentCut = t - C.SPREAD_HOURS * 3600;
  const fresh = ads.filter(a => a.start_ts && a.start_ts >= recentCut);
  const firstByShop = new Map();
  for (const a of ads) if (a.domain && a.start_ts)
    firstByShop.set(a.domain, Math.min(firstByShop.has(a.domain) ? firstByShop.get(a.domain) : a.start_ts, a.start_ts));
  const shopsNew = [...firstByShop.values()].filter(x => x >= recentCut).length;
  const adsNew = sum(fresh.map(w));
  const spreading = adsNew >= C.SPREAD_MIN_NEW_ADS || shopsNew >= C.SPREAD_MIN_NEW_SHOPS;
  const adsPerDay = adsTotal / Math.max(1.0, videoAge || 1.0);

  // Trang bán chính = link có nhiều QC nhất; tuổi trang = trang SỚM nhất trong các trang đã đọc được
  const linkCounts = new Map();
  for (const a of ads) if (a.link_url) linkCounts.set(a.link_url, (linkCounts.get(a.link_url) || 0) + 1);
  let mainLink = null, best = 0;
  for (const [u, n] of linkCounts) if (n > best) { mainLink = u; best = n; }
  const mainLanding = mainLink ? landings[mainLink] || null : null;
  const land = [...linkCounts.keys()].map(u => landings[u]).filter(l => l && l.created_ts)
    .map(l => [l.created_ts, l.date_source ?? null]).sort((x, y) => x[0] - y[0]);
  const [landingFirstTs, dateSource] = land.length ? land[0] : [null, null];
  const landingAge = daysOf(landingFirstTs, t);
  const pageOld = !!(landingFirstTs && firstTs && firstTs - landingFirstTs > C.PAGE_OLDER_THAN_VIDEO * DAY);

  const [label, checks] = makeLabel(videoAge, landingAge, pageOld, shopsActive, shopsWin, buckets);
  const longestRun = Math.max(0, ...active.map(a => daysOf(a.start_ts, t) || 0));
  const [potential, cashCow, flagChecks] = makeFlags(videoAge, pageOld, label, adsNew, pagesActive.size, longestRun,
    buckets, shopsActive.size);

  // Mọi trang đang bán sản phẩm (link trong QC), nhiều QC nhất lên trước
  const sellPages = [...linkCounts].sort((x, y) => y[1] - x[1]).slice(0, 30).map(([u, n]) => {
    const l = landings[u] || {};
    const netloc = urlparse(u).netloc.toLowerCase();
    return {url: u, ads: n, domain: netloc.startsWith("www.") ? netloc.slice(4) : netloc, platform: l.platform ?? null,
      price: l.price ?? null, compare_price: l.compare_price ?? null, created_ts: l.created_ts ?? null,
      date_source: l.date_source ?? null};
  });

  let rep = ads[0], repKey = null;
  for (const a of ads) {
    const k = [a.video_url ? 1 : 0, a.thumb_path ? 1 : 0, a.is_active || 0, w(a)];
    if (repKey === null || cmpTuple(k, repKey) > 0) { rep = a; repKey = k; }
  }
  const title = rep.body || rep.title || (mainLanding || {}).title || "(không có nội dung)";

  // POD: phân loại từ nội dung QC + link + tiêu đề trang bán
  const texts = new Set();
  for (const a of ads) for (const k of ["body", "title", "link_url"]) if (a[k]) texts.add(a[k]);
  for (const u of linkCounts.keys()) { const l = landings[u]; if (l && l.title) texts.add(l.title); }
  const [productType, niches, personalized] = classify(sortedStr(texts).join(" \n "));
  const markers = new Set();
  for (const u of linkCounts.keys()) {
    const l = landings[u];
    if (l && l.pod_markers) for (const m of l.pod_markers.split(",")) markers.add(m);
  }
  const platform = (mainLanding || {}).platform ?? null;
  const isPod = !!(productType || personalized || markers.size || POD_PLATFORMS.has(platform));
  return {
    cid,
    label,
    checks,
    title: cut(title.split("\n")[0], 300),
    body: rep.body ?? null,
    thumb: rep.thumb_path ?? null,
    thumb_url: rep.thumb_url ?? null,
    video_url: rep.video_url ?? null,
    ad_library_url: `https://www.facebook.com/ads/library/?id=${rep.ad_id}`,
    main_link: mainLink,
    price: (mainLanding || {}).price ?? null,
    compare_price: (mainLanding || {}).compare_price ?? null,
    platform,
    product_type: productType,
    niches,
    personalized,
    pod_markers: sortedStr(markers),
    is_pod: isPod,
    landing_date_source: dateSource,
    first_ts: firstTs,
    video_age_days: videoAge !== null ? pyRound(videoAge, 1) : null,
    landing_created_ts: landingFirstTs,
    landing_age_days: landingAge !== null ? pyRound(landingAge, 1) : null,
    page_old: pageOld,
    pages_active: pagesActive.size,
    pages_total: pagesAll.size,
    shops_active: shopsActive.size,
    shops_total: shopsAll.size,
    shops_win: shopsWin.length,
    shops_new_post: shopsNewPost.length,
    ads_total: adsTotal,
    ads_active: sum(active.map(w)),
    ads_gone: sum(inactive.map(w)),
    ads_per_day: pyRound(adsPerDay, 2),
    ads_new_24h: sum(fresh.filter(a => a.start_ts >= t - 86400).map(w)),
    ads_new_48h: adsNew,
    shops_new_48h: shopsNew,
    pages_new_48h: new Set(fresh.filter(a => a.page_id).map(a => a.page_id)).size,
    spreading,
    potential,
    cash_cow: cashCow,
    flag_checks: flagChecks,
    longest_run_days: pyRound(longestRun, 1),
    urls_total: linkCounts.size,
    sell_pages: sellPages,
    buckets,
    page_ids: sortedStr(pagesAll),
    shops: sortedStr(shopsAll),
    ads: [...ads].sort((x, y) => (x.start_ts || 0) - (y.start_ts || 0)).map(a => ({
      ad_id: a.ad_id, page_id: a.page_id ?? null, page_name: a.page_name ?? null, domain: a.domain ?? null,
      link_url: a.link_url ?? null, start_ts: a.start_ts ?? null, end_ts: a.end_ts ?? null, is_active: a.is_active ?? null,
      collation_count: a.collation_count ?? null})),
    keywords: sortedStr(new Set(ads.filter(a => a.keyword).map(a => a.keyword))),
    last_seen: Math.max(...ads.map(a => a.last_seen || 0)),
  };
}

function makeLabel(videoAge, landingAge, pageOld, shopsActive, shopsWin, buckets) {
  const checks = [];
  const check = (ok, text) => { checks.push({ok, text}); return ok; };
  let videoNew, videoOk;
  if (videoAge === null) {
    check(false, "Chưa rõ tuổi video");
    videoNew = videoOk = false;
  } else {
    videoNew = check(videoAge <= C.NEW_VIDEO_DAYS, `Video ${videoAge.toFixed(0)} ngày tuổi (mới nếu ≤ ${C.NEW_VIDEO_DAYS} ngày)`);
    videoOk = videoAge <= C.OLD_VIDEO_DAYS;
  }
  if (landingAge === null) checks.push({ok: null, text: "Chưa đọc được tuổi trang bán"});
  else check(!pageOld, `Trang bán ${landingAge.toFixed(0)} ngày tuổi`
    + (pageOld ? ` — cũ hơn video quá ${C.PAGE_OLDER_THAN_VIDEO} ngày` : ""));
  const manyShops = check(shopsActive.size >= C.MIN_SHOPS_SAP_WIN,
    `${shopsActive.size} shop đang chạy (cần ≥ ${C.MIN_SHOPS_SAP_WIN})`);
  const proven = check(shopsWin.length >= C.MIN_SHOPS_WIN,
    `${shopsWin.length} shop giữ QC sống ${C.SCALE_MAX_DAYS}–${C.WIN_MAX_DAYS} ngày (cần ≥ ${C.MIN_SHOPS_WIN})`);

  let label;
  if (videoAge !== null && !videoOk) label = "cu";
  else if (pageOld) label = "trang_cu";
  else if (proven && videoOk) label = "win";
  else if (videoNew && manyShops) label = "sap_win";
  else if (buckets.scale >= C.MIN_SCALE_ADS && videoOk) label = "scale";
  else label = "theo_doi";
  return [label, checks];
}

// Video Tiềm Năng (vừa nhú) và SP bò sữa (chạy đều nhiều tuần) — 2 tab riêng, không thay nhãn chính.
function makeFlags(videoAge, pageOld, label, adsNew, nPages, longestRun, buckets, nShops) {
  const young = videoAge !== null && videoAge <= C.POTENTIAL_MAX_DAYS;
  const stirring = adsNew >= C.POTENTIAL_MIN_NEW_ADS || nPages >= C.POTENTIAL_MIN_PAGES;
  const potential = young && stirring && !pageOld && !["sap_win", "win"].includes(label);
  const cashCow = videoAge !== null && videoAge >= C.COW_MIN_DAYS && longestRun >= C.COW_MIN_RUN_DAYS
    && buckets.old >= C.COW_MIN_OLD_ADS && nShops >= C.COW_MIN_SHOPS;
  const checks = [
    {ok: potential, text: `Tiềm năng: video ≤ ${C.POTENTIAL_MAX_DAYS} ngày, ≥ ${C.POTENTIAL_MIN_NEW_ADS} QC mới/48h ` +
      `hoặc ≥ ${C.POTENTIAL_MIN_PAGES} page đang chạy, chưa vào Sắp WIN / Win`},
    {ok: cashCow, text: `Bò sữa: video ≥ ${C.COW_MIN_DAYS} ngày, có QC sống ≥ ${C.COW_MIN_RUN_DAYS} ngày, ` +
      `≥ ${C.COW_MIN_OLD_ADS} QC sống > ${C.WIN_MAX_DAYS} ngày, ≥ ${C.COW_MIN_SHOPS} shop đang chạy`},
  ];
  return [potential, cashCow, checks];
}

export function buildVideos(ads, landings, t = null) {
  const clusters = cluster(ads);
  const groups = [...clusters.entries()];
  const videos = groups.map(([cid, group]) => summarize(cid, group, landings, t));
  // Cùng 1 sản phẩm thường có nhiều video khác nhau -> đếm để hiện "sản phẩm này có N video"
  const perProduct = new Map();
  videos.forEach((v, i) => {
    const keys = new Map();
    for (const a of groups[i][1]) { const k = productKey(a.link_url); if (k) keys.set(k, (keys.get(k) || 0) + 1); }
    let bestKey = null, n = 0;
    for (const [k, c] of keys) if (c > n) { bestKey = k; n = c; }
    v.product_key = bestKey;
    if (bestKey) perProduct.set(bestKey, (perProduct.get(bestKey) || 0) + 1);
  });
  for (const v of videos) v.product_videos = v.product_key ? perProduct.get(v.product_key) || 1 : 1;
  videos.sort((a, b) => b.ads_per_day - a.ads_per_day);
  return videos;
}
