// Kiểm chính máy đo của ux-shots.mjs trên trang mẫu dựng tay: mỗi luật [máy] có bố cục đúng (phải 0 vi phạm) và bố
// cục sai (phải bị bắt đúng luật). Máy đo bố cục dễ sai khi chỉ đọc code (ADR-0030: phép đo sticky sai nhiều lượt vì so
// chiều cao thay cơ chế CSS) — sửa phép đo thì thêm trường hợp ở đây rồi chạy lại; mỗi trường hợp chỉ sai đúng một chỗ,
// để bỏ một phép kiểm thì ít nhất một trường hợp hỏng. Hiện phủ K1–K3 (hộp Key numbers).
//
//   node scripts/ux-shots-fixtures.mjs        (cần trình duyệt như ux-shots: BROWSER_CHANNEL, mặc định msedge)
import { chromium } from "playwright";
import { RULES, measure } from "./ux-shots.mjs";

const CSS = `
body{font:15px/1.6 sans-serif;margin:0;padding:16px}
h2{font-size:26px;margin:0 0 16px} h4{font-size:17px;font-weight:600;margin:0}
.grid{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:24px}
.one{grid-template-columns:minmax(0,1fr)} .span{grid-column:span 2}
.bg-warm-surface{background:#fffaf0;border:1px solid #f3dfb5;padding:20px;display:flex;flex-direction:column;gap:16px}
dl{margin:0;display:flex;flex-direction:column;gap:16px} dd{margin:0}
.v{display:block;font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}
.l{display:block;font-size:15px;font-weight:600}
.n{font-size:13px} .scope{font-size:12px;font-weight:600;margin:0 0 4px}
.sticky{position:sticky;top:16px} .start{align-self:start}
.bar{height:4px;background:#b45309;margin-top:6px;width:40%}
`;
const row = (v, l, n, bar = "", { rowStyle = "", valueStyle = "", labelStyle = "" } = {}) =>
  `<div style="${rowStyle}"><dt><span class="v" data-ux="kn-value" style="${valueStyle}">${v}</span><span class="l" data-ux="kn-label" style="${labelStyle}">${l}</span></dt><dd class="n">${n}</dd>${bar}</div>`;
// 3 dòng, dòng giữa mang 1 chỗ sai — mỗi trường hợp chỉ sai đúng 1 phép kiểm (bỏ phép đó thì trường hợp hỏng)
const withMiddle = (opts) => row("169", "content units", "All.") + row("163", "with text", "6 have no text.", "", opts) + row("110", "in topics", "53 unclustered.");
const rows = row("169", "content units", "Every unit collected so far.") + row("163", "with text", "6 have no text.") + row("110", "in 13 topics", "53 stay unclustered.");
const left = (h) => `<div><p style="margin:0;height:${h}px">Answer and bullets.</p></div>`;
const box = (cls, inner = rows, attrs = 'data-ux="key-numbers"') =>
  `<div class="bg-warm-surface ${cls}" ${attrs}><h4>Key numbers</h4><dl>${inner}</dl></div>`;
// <!doctype html>: chế độ chuẩn như trang Next thật (thiếu → quirks mode, chiều cao dòng/phần trăm tính khác)
const page = (body, width = 1200) =>
  `<!doctype html><style>${CSS}</style><main style="width:${width}px"><section><h2>Block</h2>${body}</section></main>`;
const below = `<div class="span"><p style="margin:0;height:1200px">Long block under both columns.</p></div>`;

// [tên, HTML, các "luật|loại" K mong đợi, vị trí cuộn trước khi đo (px)]
const CASES = [
  ["A đúng: cột trái dài", page(`<div class="grid">${left(700)}${box("sticky start")}</div>`), []],
  ["B đúng: hộp cao hơn cột trái", page(`<div class="grid">${left(40)}${box("sticky start")}</div>`), []],
  [
    "C đúng: data-ux ở phần bọc + dòng phạm vi",
    page(`<div class="grid">${left(700)}<div class="sticky start" data-ux="key-numbers"><p class="scope">SELECTED TOPIC · Career</p>${box("", rows, "")}</div></div>`),
    [],
  ],
  [
    "D đúng: thanh tỉ lệ ở dòng cuối",
    page(`<div class="grid">${left(700)}${box("sticky start", row("169", "units", "All.") + row("110", "in topics", "67% of 163", '<div class="bar" aria-hidden="true"></div>'))}</div>`),
    [],
  ],
  ["E đúng: 1 cột (màn hình hẹp), không dính", page(`<div class="grid one">${left(300)}${box("")}</div>`, 360), []],
  ["F sai: kéo giãn + rải đều (kiểu cũ)", page(`<div class="grid">${left(700)}<div class="bg-warm-surface" data-ux="key-numbers"><h4>Key numbers</h4><dl style="flex:1;justify-content:space-evenly">${rows}</dl></div></div>`), ["K3|spread", "K3|stretch", "K3|sticky"]],
  ["G sai: sticky nhưng thiếu self-start", page(`<div class="grid">${left(700)}${box("sticky")}</div>`), ["K3|sticky", "K3|stretch"]],
  [
    "H sai: hộp tự viết, tên riêng, số 15px căn phải",
    page(`<div class="grid">${left(700)}<div class="bg-warm-surface sticky start"><h4>This topic in numbers</h4><dl><div style="display:flex;justify-content:space-between"><dt class="l">Median rate</dt><dd style="font-weight:700;font-variant-numeric:tabular-nums">2.42%</dd></div></dl></div></div>`),
    ["K1|component", "K1|title", "K2|row"],
  ],
  ["I sai: hộp dính chung lưới với khối bên dưới", page(`<div class="grid">${left(300)}${box("sticky start")}${below}</div>`), ["K3|sticky-overlap"]],
  ["J đúng: ô bọc bị kéo giãn, hộp dính bên trong cao nhất hàng", page(`<div class="grid">${left(40)}<div>${box("sticky")}</div></div>`), []],
  ["K đúng: hộp ở cột chính, hàng trên trải 2 cột", page(`<div class="grid"><div class="span"><p style="margin:0">Header row.</p></div>${box("start")}${left(700)}</div>`), []],
  ["L sai: tổ tiên overflow hidden — không dính theo trang", page(`<div style="overflow:hidden"><div class="grid">${left(700)}${box("sticky start")}</div></div>`), ["K3|sticky"]],
  ["M đúng: khối bên dưới đặt ngoài lưới", page(`<div class="grid">${left(300)}${box("sticky start")}</div>${below}`), []],
  ["I2 sai: như I, trang đã cuộn trước khi đo", page(`<div class="grid">${left(300)}${box("sticky start")}${below}</div>`), ["K3|sticky-overlap"], 700],
  ["N sai: 5 số trong 1 hộp", page(`<div class="grid">${left(900)}${box("sticky start", rows + row("53", "unclustered", "x") + row("13", "topics", "y"))}</div>`), ["K2|count"]],
  ["O sai: khoảng giữa các dòng lệch", page(`<div class="grid">${left(700)}${box("sticky start", withMiddle({ rowStyle: "margin-top:20px" }))}</div>`), ["K3|rhythm"]],
  ["P sai: dòng flex-grow", page(`<div class="grid">${left(700)}${box("sticky start", withMiddle({ rowStyle: "flex:1" }))}</div>`), ["K3|spread"]],
  ["Q sai: sticky không có top", page(`<div class="grid">${left(700)}${box("start", rows, 'data-ux="key-numbers" style="position:sticky"')}</div>`), ["K3|sticky"]],
  ["R sai: không dính, khối bên dưới trong lưới", page(`<div class="grid">${left(700)}${box("start")}${below}</div>`), ["K3|sticky"]],
  [
    "A2 sai: dòng phạm vi trong phần bọc, sticky đặt ở khung bên trong (sát đáy phần bọc — không trượt được)",
    page(`<div class="grid">${left(700)}<div class="start" data-ux="key-numbers"><p class="scope">SELECTED TOPIC · Career</p>${box("sticky", rows, "")}</div></div>`),
    ["K3|sticky"],
  ],
  [
    "B2 sai: hàng trên trải 2 cột, ô dính bị kéo giãn ở hàng cuối (sát đáy lưới — không trượt được)",
    page(`<div class="grid"><div class="span"><p style="margin:0">Header row.</p></div>${left(700)}<div class="sticky">${box("", rows, 'data-ux="key-numbers"')}</div></div>`),
    ["K3|sticky"],
  ],
  [
    "A3 sai: như A2, khung có margin-bottom (sticky giới hạn theo margin box — vẫn không trượt)",
    page(`<div class="grid">${left(700)}<div class="start" data-ux="key-numbers"><p class="scope">SELECTED TOPIC · Career</p>${box("sticky", rows, 'style="margin-bottom:16px"')}</div></div>`),
    ["K3|sticky"],
  ],
  [
    "B3 đúng: hộp cao nhất hàng, chú thích dưới khung trong cùng ô",
    page(`<div class="grid">${left(40)}<div class="start" data-ux="key-numbers">${box("", rows, "")}<p class="n" style="margin:8px 0 0">Source: latest snapshot.</p></div></div>`),
    [],
  ],
  [
    "B4 đúng: như B3, ô bên cạnh là flex hàng ngang (con bị kéo cao theo hàng — không có gì để cuộn qua)",
    page(`<div class="grid"><div style="display:flex"><p style="margin:0;height:40px">Short.</p></div><div class="start" data-ux="key-numbers">${box("", rows, "")}<p class="n" style="margin:8px 0 0">Source: latest snapshot.</p></div></div>`),
    [],
  ],
  [
    "B5 sai: ô bên cạnh có con cuối margin-bottom lớn (cao hơn hộp), hộp không dính",
    page(`<div class="grid"><div><p style="margin:0 0 700px;height:40px">Short text, long margin.</p></div>${box("start")}</div>`),
    ["K3|sticky"],
  ],
  ["L2 sai: tổ tiên overflow hidden + khối bên dưới trong lưới — không dính, không đè", page(`<div style="overflow:hidden"><div class="grid">${left(700)}${box("sticky start")}${below}</div></div>`), ["K3|sticky"]],
  ["S đúng: khối bên dưới chỉ nằm dưới cột chính", page(`<div class="grid">${left(300)}${box("sticky start")}<div><p style="margin:0;height:1200px">Under the main column only.</p></div></div>`), []],
  ["T sai: lưới 1 cột lồng trong cột phụ, không dính", page(`<div class="grid">${left(700)}<div class="grid one start">${box("")}</div></div>`), ["K3|sticky"]],
  ["U sai: chỉ số 15px", page(`<div class="grid">${left(700)}${box("sticky start", withMiddle({ valueStyle: "font-size:15px" }))}</div>`), ["K2|row"]],
  ["V sai: chỉ nhãn cùng dòng với số", page(`<div class="grid">${left(700)}${box("sticky start", withMiddle({ valueStyle: "display:inline", labelStyle: "display:inline;margin-left:8px" }))}</div>`), ["K2|row"]],
  ["W sai: chỉ số căn phải", page(`<div class="grid">${left(700)}${box("sticky start", withMiddle({ valueStyle: "text-align:right" }))}</div>`), ["K2|row"]],
  [
    "X sai: chỉ nhãn nằm trên số",
    page(`<div class="grid">${left(700)}${box("sticky start", row("169", "units", "All.") + '<div><dt><span class="l" data-ux="kn-label">with text</span><span class="v" data-ux="kn-value">163</span></dt><dd class="n">6 have no text.</dd></div>' + row("110", "in topics", "x"))}</div>`),
    ["K2|row"],
  ],
  ["Y sai: chỉ nhãn 13px", page(`<div class="grid">${left(700)}${box("sticky start", withMiddle({ labelStyle: "font-size:13px" }))}</div>`), ["K2|row"]],
  ["Z sai: phần tử dính nằm sâu, bằng khối chứa nó", page(`<div class="grid">${left(700)}<div class="start"><div>${box("sticky")}</div></div></div>`), ["K3|sticky"]],
  ["AA sai: ô dính bị kéo giãn, lưới nhiều hàng — vẫn trượt đè khối dưới", page(`<div class="grid">${left(600)}${box("sticky")}${below}</div>`), ["K3|stretch", "K3|sticky-overlap"]],
];

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL ?? "msedge" });
let failed = 0;
for (const [name, html, expect, scroll = 0] of CASES) {
  const tab = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await tab.setContent(html);
  if (scroll) await tab.evaluate((y) => window.scrollTo(0, y), scroll);
  const { violations } = await tab.evaluate(measure, { tier: "app", rules: RULES });
  const k = violations.filter((v) => v.rule.startsWith("K"));
  const got = [...new Set(k.map((v) => v.key.split("|").slice(0, 2).join("|")))].sort();
  const ok = JSON.stringify(got) === JSON.stringify([...expect].sort());
  if (!ok) failed++;
  console.log(`${ok ? "OK  " : "FAIL"} ${name} → ${got.join(", ") || "0 vi phạm K"}${ok ? "" : ` (mong đợi: ${expect.join(", ") || "0"})`}`);
  if (!ok) for (const v of k) console.log(`       ${v.detail}`);
  await tab.close();
}
await browser.close();
console.log(failed ? `Máy đo: ${failed}/${CASES.length} trường hợp sai` : `Máy đo: ${CASES.length}/${CASES.length} trường hợp đúng`);
process.exitCode = failed ? 1 : 0;
