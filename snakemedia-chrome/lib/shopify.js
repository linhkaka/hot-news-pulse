// Kết nối Shopify + Clone sản phẩm vào store của bạn (giống snakepod/shopify.py).
//
// Kết nối: app tự tạo trong Shopify Dev Dashboard (Client ID + Client secret, cài vào store của bạn) -> lấy mã truy cập
// bằng "client credentials" (hết hạn sau ~24 giờ, tiện ích tự lấy lại). Hoặc dán thẳng Admin API access token (shpat_...)
// của custom app tạo trong Shopify admin.
//
// Clone: đọc sản phẩm của trang bán (Shopify: /products/<handle>.json; nền tảng khác: thẻ og: trong trang)
// rồi tạo sản phẩm NHÁP (Draft) trong store của bạn qua Admin GraphQL `productSet`. Không tự đăng bán.
import {C, URLS} from "./config.js";
import * as db from "./db.js";
import {TITLE_RE, priceFromHtml} from "./landing.js";

const SHOP_RE = /^[a-z0-9][a-z0-9-]*\.myshopify\.com$/;
const OG_RE = /<meta[^>]+(?:property|name)=["'](og:[a-z:_]+|product:price:amount|twitter:image)["'][^>]*>/gi;
const CONTENT_RE = /content=["']([^"']*)["']/i;
const DANGER_RE = /<(script|style|iframe|object|embed)[^>]*>[\s\S]*?<\/\1\s*>|<(script|iframe|object|embed)[^>]*\/?>/gi;
const ON_RE = /\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi;
const ENT = {amp: "&", lt: "<", gt: ">", quot: '"', apos: "'"};
const unescape = s => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => e[0] === "#"
  ? String.fromCodePoint(e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : +e.slice(1)) : ENT[e.toLowerCase()] ?? m);
const escapeHtml = s => s.replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;"}[c]));

export const MUTATION = `mutation productSet($input: ProductSetInput!, $synchronous: Boolean!) {
  productSet(synchronous: $synchronous, input: $input) {
    product { id handle title }
    userErrors { field message code }
  }
}`;

export class ShopifyError extends Error {}

// 'ten-store', 'https://ten-store.myshopify.com/admin' -> 'ten-store.myshopify.com'
export function shopDomain(raw) {
  let s = String(raw || "").trim().toLowerCase().replace(/^https?:\/\//, "").split("/")[0];
  if (s && !s.includes(".")) s += ".myshopify.com";
  if (URLS.SHOPIFY_BASE) return s;                  // kiểm thử: chấp nhận mọi tên
  if (!SHOP_RE.test(s)) throw new ShopifyError("Tên store phải có dạng ten-store.myshopify.com (xem ở Shopify admin → Settings → Domains)");
  return s;
}

const base = shop => URLS.SHOPIFY_BASE || `https://${shop}`;
export const settings = () => db.getSetting("shopify", {});

export async function status() {
  const s = await settings(), secret = s.secret || "";
  return {connected: !!s.name, shop: s.shop ?? null, name: s.name ?? null, currency: s.currency ?? null, client_id: s.client_id ?? null,
    secret_masked: secret.length > 10 ? secret.slice(0, 4) + "…" + secret.slice(-4) : !!secret,
    scopes: C.SHOPIFY_SCOPES, clones: Object.keys(await db.getSetting("clones", {})).length};
}

async function token(s) {
  const secret = s.secret || "";
  if (secret.startsWith("shpat_")) return secret;   // Admin API access token dán thẳng
  if (s.token && (s.token_exp || 0) > db.now() + 300) return s.token;
  if (!s.client_id) throw new ShopifyError("Thiếu Client ID");
  const r = await fetch(`${base(s.shop)}/admin/oauth/access_token`, {method: "POST", credentials: "omit",
    body: new URLSearchParams({grant_type: "client_credentials", client_id: s.client_id, client_secret: secret})});
  if (r.status !== 200) throw new ShopifyError(`Shopify từ chối Client ID / Client secret (mã ${r.status}). Kiểm tra app đã được ` +
    "cài (Install app) vào đúng store này chưa.");
  const j = await r.json();
  s.token = j.access_token;
  s.token_exp = db.now() + Math.trunc(j.expires_in || 86399);
  if (s.name) await db.setSetting("shopify", s);    // đã kết nối: lưu mã mới để dùng lại
  return s.token;
}

export async function gql(s, query, variables = {}) {
  let r;
  try {
    const tok = await token(s);
    r = await fetch(`${base(s.shop)}/admin/api/${C.SHOPIFY_API_VERSION}/graphql.json`, {method: "POST", credentials: "omit",
      headers: {"Content-Type": "application/json", "X-Shopify-Access-Token": tok}, body: JSON.stringify({query, variables})});
  } catch (e) {
    if (e instanceof ShopifyError) throw e;
    throw new ShopifyError(`Không gọi được Shopify: ${e.message}`);
  }
  if (r.status === 401 || r.status === 403) throw new ShopifyError("Mã truy cập không hợp lệ hoặc thiếu quyền write_products. Kết nối lại.");
  if (!r.ok) throw new ShopifyError(`Không gọi được Shopify: mã ${r.status}`);
  const j = await r.json();
  if (j.errors && j.errors.length) throw new ShopifyError("Shopify báo lỗi: " + j.errors.map(e => e.message || String(e)).join("; ").slice(0, 300));
  return j.data;
}

export async function connect(shop, clientId, secret) {
  shop = shopDomain(shop);
  const old = await settings();
  if (!secret && old.shop === shop) secret = old.secret;   // để trống = giữ secret cũ
  if (!secret) throw new ShopifyError("Nhập Client secret (hoặc Admin API access token shpat_...)");
  const s = {shop, client_id: String(clientId || "").trim(), secret: secret.trim()};
  const data = await gql(s, "{ shop { name myshopifyDomain currencyCode } }");
  Object.assign(s, {name: data.shop.name, currency: data.shop.currencyCode ?? null});
  await db.setSetting("shopify", s);
  return status();
}

export const disconnect = () => db.setSetting("shopify", {});

// ---------------- đọc sản phẩm nguồn ----------------

export const cleanHtml = h => (h || "").replace(DANGER_RE, "").replace(ON_RE, "");

function money(v) {
  if (v === null || v === undefined || v === "") return null;
  const x = Number(v);
  return Number.isFinite(x) && x >= 0 ? x.toFixed(2) : null;
}

// Sản phẩm từ /products/<handle>.json của Shopify
export function fromShopifyJson(p, url) {
  const opts = (p.options || []).map((o, i) => ({name: o.name || `Option ${i + 1}`, values: [...new Set(o.values || [])]}));
  const variants = (p.variants || []).slice(0, C.CLONE_MAX_VARIANTS).map(v => ({
    options: opts.map((_, i) => v[`option${i + 1}`] ?? null), price: money(v.price) || "0.00", compare_at_price: money(v.compare_at_price)}));
  let tags = p.tags || [];
  if (typeof tags === "string") tags = tags.split(",").map(t => t.trim()).filter(Boolean);
  const imgs = (p.images || []).map(i => i.src).filter(Boolean).map(u => u.startsWith("//") ? "https:" + u : u);
  return {title: p.title || "Sản phẩm", body_html: cleanHtml(p.body_html), vendor: p.vendor ?? null, product_type: p.product_type ?? null,
    tags, options: opts, variants, images: imgs.slice(0, C.CLONE_MAX_IMAGES), source_url: url};
}

// Nền tảng khác: đọc thẻ og:title / og:description / og:image / giá trong trang
export function fromHtml(page, url) {
  const meta = {}, images = [];
  for (const m of page.matchAll(OG_RE)) {
    const c = CONTENT_RE.exec(m[0]);
    if (!c) continue;
    const k = m[1].toLowerCase(), val = unescape(c[1]).trim();
    if (["og:image", "og:image:secure_url", "twitter:image"].includes(k)) images.push(val.startsWith("//") ? "https:" + val : val);
    else if (!(k in meta)) meta[k] = val;
  }
  const t = TITLE_RE.exec(page);
  const title = meta["og:title"] || (t ? unescape(t[1]).trim() : null) || "Sản phẩm";
  const price = money(meta["product:price:amount"] || meta["og:price:amount"]) || money(priceFromHtml(page)) || "0.00";
  const desc = meta["og:description"];
  return {title: title.slice(0, 255), body_html: desc ? `<p>${escapeHtml(desc)}</p>` : "", vendor: null, product_type: null, tags: [],
    options: [], variants: [{options: [], price, compare_at_price: null}],
    images: [...new Set(images.filter(u => u.startsWith("http")))].slice(0, C.CLONE_MAX_IMAGES), source_url: url};
}

export async function sourceProduct(url) {
  let r;
  try {
    r = await fetch(url, {credentials: "omit", redirect: "follow"});
    if (!r.ok) throw new Error(`mã ${r.status}`);
  } catch (e) { throw new ShopifyError(`Không đọc được trang bán: ${e.message}`); }
  const final = new URL(r.url || url);
  const m = /\/products\/([^/?#]+)/.exec(final.pathname);
  if (m) {
    try {
      const j = await fetch(`${final.origin}/products/${m[1]}.json`, {credentials: "omit"});
      if (j.status === 200 && (j.headers.get("content-type") || "").includes("json"))
        return fromShopifyJson((await j.json()).product || {}, url);
    } catch {}
  }
  return fromHtml(await r.text(), url);
}

// Dữ liệu sản phẩm -> ProductSetInput (luôn ở trạng thái DRAFT)
export function productInput(src) {
  let opts = src.options.filter(o => o.values.length);
  let variants = src.variants.length ? src.variants : [{options: [], price: "0.00", compare_at_price: null}];
  if (!opts.length) {                              // sản phẩm 1 biến thể: Shopify vẫn cần 1 tuỳ chọn "Title"
    opts = [{name: "Title", values: ["Default Title"]}];
    variants = [{...variants[0], options: ["Default Title"]}];
  }
  const outVars = [], seen = new Set();
  for (const v of variants) {
    const raw = [...v.options, ...Array(opts.length).fill(null)].slice(0, opts.length);
    const vals = raw.map((x, i) => x || opts[i].values[0]);
    const k = JSON.stringify(vals);
    if (seen.has(k)) continue;
    seen.add(k);
    const item = {optionValues: opts.map((o, i) => ({optionName: o.name, name: vals[i]})), price: v.price};
    if (v.compare_at_price && Number(v.compare_at_price) > Number(v.price)) item.compareAtPrice = v.compare_at_price;
    outVars.push(item);
  }
  const used = Object.fromEntries(opts.map(o => [o.name,
    new Set(outVars.flatMap(v => v.optionValues.filter(ov => ov.optionName === o.name).map(ov => ov.name)))]));
  const inp = {title: src.title.slice(0, 255), descriptionHtml: src.body_html || "", status: "DRAFT",
    tags: [...new Set([...src.tags.slice(0, 40), "snakemedia-clone"])],
    productOptions: opts.map((o, i) => ({name: o.name, position: i + 1, values: o.values.filter(x => used[o.name].has(x)).map(x => ({name: x}))})),
    variants: outVars,
    files: src.images.map(u => ({originalSource: u, contentType: "IMAGE", alt: src.title.slice(0, 255)}))};
  if (src.vendor) inp.vendor = src.vendor.slice(0, 255);
  if (src.product_type) inp.productType = src.product_type.slice(0, 255);
  return inp;
}

export const adminUrl = (shop, gid) => `https://admin.shopify.com/store/${shop.split(".")[0]}/products/${gid.split("/").pop()}`;

export async function clone(url, cid = null) {
  const s = await settings();
  if (!s.name) throw new ShopifyError("Chưa kết nối Shopify (Cài đặt → Kết nối Shopify)");
  const src = await sourceProduct(url);
  const inp = productInput(src);
  const data = await gql(s, MUTATION, {input: inp, synchronous: true});
  const res = data.productSet;
  if (res.userErrors && res.userErrors.length)
    throw new ShopifyError("Shopify không nhận sản phẩm: " + res.userErrors.map(e => e.message).join("; ").slice(0, 400));
  const p = res.product;
  const rec = {url, product_id: p.id, title: p.title || src.title, admin_url: adminUrl(s.shop, p.id), shop: s.shop, ts: db.now(),
    images: src.images.length, variants: inp.variants.length};
  if (cid) {
    const clones = await db.getSetting("clones", {});
    clones[cid] = rec;
    await db.setSetting("clones", clones);
  }
  return rec;
}
