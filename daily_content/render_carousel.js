// LinkedIn carousel: slides JSON -> 1080x1350 PDF (one slide per page), HOI palette.
//   node daily_content/render_carousel.js <day.json> <out.pdf>
// day.json: { "date": "2026-11-04", "carousel": { "slides": [ {type, ...} ], "source": "..." } }
// Slide types: cover {kicker, title, sub} | fact {label, big, text} | list {title, items[]} |
//              note {title, text} | close {title, text, cta}
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const FONTS = path.join(__dirname, "..", "fonts");
const font = (name, file) =>
  `@font-face{font-family:'${name}';src:url(data:font/ttf;base64,${fs.readFileSync(path.join(FONTS, file)).toString("base64")}) format('truetype')}`;
const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const noDash = (s) => s.replace(/[–—]/g, ",");

function slideHtml(s, i, n, source) {
  const dark = s.type === "cover" || s.type === "close";
  const foot = `<div class="foot"><span>HOUSE OF INVESTORS · REAL ESTATE WEALTH HOUSE · HYDERABAD</span><span>${i + 1} / ${n}</span></div>`;
  let body = "";
  if (s.type === "cover")
    body = `<div class="kicker">${esc(s.kicker)}</div><h1>${esc(s.title)}</h1><p class="sub">${esc(s.sub)}</p><div class="swipe">Swipe →</div>`;
  else if (s.type === "fact")
    body = `<div class="kicker">${esc(s.label)}</div><div class="big">${esc(s.big)}</div><p class="txt">${esc(s.text)}</p>`;
  else if (s.type === "list")
    body = `<h2>${esc(s.title)}</h2><ol>${(s.items || []).map((x, k) => `<li><b>${String(k + 1).padStart(2, "0")}</b><span>${esc(x)}</span></li>`).join("")}</ol>`;
  else if (s.type === "note")
    body = `<h2>${esc(s.title)}</h2><div class="note"><div class="kicker">HOI WEALTH DESK NOTE</div><p>${esc(s.text)}</p></div>`;
  else if (s.type === "close")
    body = `<h1 class="sm">${esc(s.title)}</h1><p class="sub">${esc(s.text)}</p><div class="cta">${esc(s.cta)}</div>`;
  const src = i === n - 1 && source ? `<div class="src">${esc(source)}</div>` : "";
  return `<section class="slide ${dark ? "dark" : ""}"><div class="rule"></div><div class="body">${body}</div>${src}${foot}</section>`;
}

async function main() {
  const [, , inFile, outFile] = process.argv;
  const day = JSON.parse(fs.readFileSync(inFile, "utf8"));
  const c = day.carousel;
  const css = `${font("Serif", "DMSerifDisplay-Regular.ttf")}${font("Sans", "InstrumentSans-Regular.ttf")}${font("SansB", "InstrumentSans-SemiBold.ttf")}
  @page{size:1080px 1350px;margin:0} *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Sans',Arial,sans-serif;color:#1A1A1A}
  .slide{width:1080px;height:1350px;background:#F7F3EC;position:relative;padding:150px 96px 230px;page-break-after:always;overflow:hidden;display:flex;flex-direction:column;justify-content:center}
  .slide.dark{background:#1A1A1A;color:#F7F3EC}
  .rule{position:absolute;top:72px;left:96px;width:120px;height:2px;background:#B48A3C}
  .body{width:100%}
  .kicker{font-family:'SansB';font-size:24px;letter-spacing:5px;text-transform:uppercase;color:#B48A3C;margin-bottom:36px}
  h1{font-family:'Serif';font-weight:400;font-size:96px;line-height:1.02;margin-bottom:44px}
  h1.sm{font-size:84px}
  h2{font-family:'Serif';font-weight:400;font-size:72px;line-height:1.08;margin-bottom:56px}
  .sub{font-size:36px;line-height:1.4;color:#6E6A63}.dark .sub{color:#CFC8BB}
  .big{font-family:'Serif';font-size:150px;line-height:1;color:#B48A3C;margin-bottom:40px}
  .txt{font-size:40px;line-height:1.38}
  ol{list-style:none} li{display:flex;gap:30px;font-size:36px;line-height:1.35;padding:26px 0;border-top:1.5px solid #D9CFBD}
  li b{font-family:'Serif';font-weight:400;color:#B48A3C;font-size:44px;min-width:64px}
  .note{border-left:3px solid #B48A3C;padding:10px 0 10px 40px}.note p{font-family:'Serif';font-size:50px;line-height:1.25}
  .cta{display:inline-block;margin-top:56px;border:2px solid #B48A3C;color:#B48A3C;font-family:'SansB';font-size:30px;letter-spacing:3px;text-transform:uppercase;padding:26px 40px}
  .swipe{margin-top:70px;font-family:'SansB';font-size:28px;letter-spacing:4px;color:#B48A3C;text-transform:uppercase}
  .src{position:absolute;left:96px;right:96px;bottom:140px;font-size:22px;line-height:1.4;color:#8E887E}
  .foot{position:absolute;left:96px;right:96px;bottom:70px;display:flex;justify-content:space-between;border-top:1px solid #B48A3C;padding-top:22px;font-family:'SansB';font-size:19px;letter-spacing:3px;color:#8E887E}`;
  const html = noDash(`<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${c.slides
    .map((s, i) => slideHtml(s, i, c.slides.length, c.source)).join("")}</body></html>`);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  await page.setContent(html, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: outFile, width: "1080px", height: "1350px", printBackground: true });
  if (process.env.PREVIEW) await page.screenshot({ path: process.env.PREVIEW, fullPage: true });
  await browser.close();
  console.log("wrote", outFile);
}
main().catch((e) => { console.error(e); process.exit(1); });
