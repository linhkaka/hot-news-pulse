// Giải mã ký tự HTML (&amp; &rsquo; &#8217; ...) giống html.unescape của Python cho các ký tự hay gặp trên trang bán.
const NAMED = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", rsquo: "’", lsquo: "‘", rdquo: "”",
  ldquo: "“", sbquo: "‚", bdquo: "„", ndash: "–", mdash: "—", hellip: "…", bull: "•",
  middot: "·", trade: "™", reg: "®", copy: "©", deg: "°", times: "×", divide: "÷",
  euro: "€", pound: "£", yen: "¥", cent: "¢", sect: "§", para: "¶", laquo: "«",
  raquo: "»", frac12: "½", frac14: "¼", frac34: "¾", plusmn: "±", hearts: "♥", star: "☆",
  eacute: "é", egrave: "è", ecirc: "ê", aacute: "á", agrave: "à", acirc: "â", atilde: "ã",
  auml: "ä", ouml: "ö", uuml: "ü", oacute: "ó", iacute: "í", uacute: "ú", ntilde: "ñ",
  ccedil: "ç", szlig: "ß", Eacute: "É", Auml: "Ä", Ouml: "Ö", Uuml: "Ü", ensp: " ",
  emsp: " ", thinsp: " ", zwj: "‍", zwnj: "‌", shy: "­",
};

export function unescape(s) {
  return String(s).replace(/&(#[xX][0-9a-fA-F]+|#\d+|[A-Za-z][A-Za-z0-9]*);/g, (m, e) => {
    if (e[0] !== "#") return NAMED[e] ?? m;
    const cp = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
    if (!cp || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) return "�";   // mã hỏng -> ký tự thay thế, không lỗi
    return String.fromCodePoint(cp);
  });
}
