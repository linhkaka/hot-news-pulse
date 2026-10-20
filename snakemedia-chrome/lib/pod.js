// Nhận diện sản phẩm POD (print-on-demand) từ nội dung QC, link và trang bán (giống snakepod/pod.py).
// Toàn bộ là luật từ khoá, đọc được, sửa được: thêm từ vào các bảng bên dưới là xong.

// Loại sản phẩm POD -> các từ khoá (tiếng Anh, vì QC chạy US)
export const PRODUCT_TYPES = {
  "Áo": ["t-shirt", "tshirt", "tee", "shirt", "hoodie", "sweatshirt", "sweater", "tank top", "polo", "jersey",
    "crewneck", "long sleeve"],
  "Cốc / Ly": ["mug", "tumbler", "cup", "glass", "wine glass", "stanley", "water bottle", "can cooler"],
  "Tranh / Poster": ["poster", "canvas", "wall art", "print", "framed", "metal sign", "wood sign", "plaque"],
  "Chăn / Gối": ["blanket", "quilt", "throw", "pillow", "cushion", "bedding", "duvet"],
  "Ornament": ["ornament", "acrylic ornament", "christmas ornament", "suncatcher"],
  "Trang trí nhà": ["doormat", "door mat", "rug", "flag", "garden flag", "house flag", "night light", "lamp",
    "led sign", "wind chime", "clock", "coaster"],
  "Phụ kiện": ["hat", "cap", "trucker", "phone case", "tote", "bag", "keychain", "socks", "necklace",
    "bracelet", "jewelry", "sticker", "magnet", "apron"],
};
export const PERSONALIZED = ["personalized", "personalised", "custom name", "your name", "customize", "customized", "custom photo",
  "upload your photo", "with name", "name and", "add your", "engraved", "monogram", "custom text"];

// Niche (đối tượng / sở thích / dịp)
export const NICHES = {
  "Chó": ["dog", "puppy", "doggo", "golden retriever", "corgi", "dachshund", "pitbull", "german shepherd"],
  "Mèo": ["cat", "kitten", "kitty"],
  "Mẹ": ["mom", "mother", "mama", "mommy"],
  "Bố": ["dad", "father", "daddy", "papa"],
  "Ông bà": ["grandma", "grandpa", "nana", "papa bear", "grandkids", "grandchildren", "mimi", "gigi"],
  "Vợ chồng / Cặp đôi": ["wife", "husband", "couple", "anniversary", "valentine", "soulmate", "boyfriend",
    "girlfriend"],
  "Y tá / Bác sĩ": ["nurse", "nursing", "doctor", "medical", "rn ", "icu"],
  "Giáo viên": ["teacher", "teaching", "classroom", "school"],
  "Cựu binh / Quân đội": ["veteran", "military", "army", "navy", "marine", "air force", "patriot"],
  "Câu cá": ["fishing", "fisherman", "bass", "angler"],
  "Săn bắn": ["hunting", "hunter", "deer"],
  "Cắm trại": ["camping", "camper", "rv ", "hiking", "outdoor"],
  "Làm vườn": ["garden", "gardening", "plant", "flower"],
  "Thể thao": ["football", "baseball", "basketball", "softball", "soccer", "hockey", "golf", "volleyball"],
  "Tôn giáo": ["jesus", "christian", "faith", "god ", "bible", "blessed", "pray"],
  "Giáng sinh": ["christmas", "xmas", "santa", "holiday"],
  "Halloween": ["halloween", "spooky", "witch", "pumpkin"],
  "Lễ Tạ ơn": ["thanksgiving", "thankful"],
  "Ngày của Mẹ/Bố": ["mother's day", "mothers day", "father's day", "fathers day"],
  "Sinh nhật": ["birthday", "bday"],
  "Tưởng niệm": ["memorial", "in loving memory", "heaven", "rest in peace", "angel wings"],
  "Nghề nghiệp": ["trucker", "electrician", "lineman", "mechanic", "firefighter", "police", "welder", "farmer"],
  "Xe / Moto": ["truck", "jeep", "motorcycle", "biker", "car guy", "tractor"],
  "Đồ uống": ["wine", "beer", "coffee", "whiskey", "bourbon"],
};

// Nền tảng hay dùng cho POD (dấu hiệu tìm trong HTML trang bán)
export const POD_PLATFORM_MARKERS = {
  gearlaunch: ["gearlaunch"], teechip: ["teechip"], shopbase: ["shopbase"], printify: ["printify"],
  printful: ["printful"], customily: ["customily"], teeinblue: ["teeinblue"], gelato: ["gelato"],
  merchize: ["merchize"], burgerprints: ["burgerprints"], senprints: ["senprints"],
};
export const POD_PLATFORMS = new Set(["gearlaunch", "teechip", "shopbase", "printify", "printful", "customily", "teeinblue",
  "gelato", "merchize", "burgerprints", "senprints"]);

const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const compile = table => Object.entries(table).map(([k, words]) =>
  [k, new RegExp("\\b(" + words.map(w => reEsc(w.trim())).join("|") + ")s?\\b", "gi")]);

const TYPES = compile(PRODUCT_TYPES);
const NICHE_RES = compile(NICHES);
const PERSONAL = new RegExp("\\b(" + PERSONALIZED.map(reEsc).join("|") + ")", "i");

// Trả về [loại sản phẩm hoặc null, [niche...], có cá nhân hoá không]
export function classify(text) {
  text = (text || "").replace(/[-_]/g, " ");
  let productType = null, best = 0;
  for (const [name, rx] of TYPES) {
    const hits = (text.match(rx) || []).length;
    if (hits > best) { productType = name; best = hits; }
  }
  const niches = NICHE_RES.filter(([, rx]) => { rx.lastIndex = 0; return rx.test(text); }).map(([name]) => name);
  return [productType, niches, PERSONAL.test(text)];
}

export function detectPodMarkers(html) {
  const h = (html || "").toLowerCase();
  return Object.entries(POD_PLATFORM_MARKERS).filter(([, marks]) => marks.some(m => h.includes(m))).map(([n]) => n).sort();
}
