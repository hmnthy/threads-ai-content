// Chụp trang cho @agent-ux-reviewer: toàn trang ở 3 khổ + từng khối của <main> ở khổ rộng, ở 2 trạng thái
// (như người xem thấy lúc mở trang / mọi khối thu gọn đã mở). Kèm máy đo theo sổ luật UI/UX
// (docs/claude/design-system.md §3b, mã luật T/L/C/A): `violations` = luật [máy], còn ≥ 1 thì UX gate FAIL;
// `warnings` = luật [máy·gợi ý], reviewer xác nhận trên ảnh. Ảnh + report.json lưu ở data/ux-shots/
// (gitignored, riêng tư). Cần `npm run dev` đang chạy (hoặc BASE_URL trỏ server khác).
//
//   node scripts/ux-shots.mjs                   (không đối số = mọi trang: so "cùng vai cùng kiểu" giữa trang, T3)
//   node scripts/ux-shots.mjs topics            (route không cần "/"; "landing" = "/")
//   BASE_URL=http://localhost:3100 node scripts/ux-shots.mjs topics analytics
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
// Mọi trang của sản phẩm — thêm trang mới vào đây (luật T3 so các trang với nhau)
const ALL_ROUTES = ["/", "/overview", "/analytics", "/topics"];
// Git Bash đổi "/topics" thành "C:/Program Files/Git/topics" (MSYS path conversion) — bỏ phần đó
const args = process.argv.slice(2).map((arg) => {
  const route = arg.replace(/^[A-Za-z]:\/.*?\/Git(?=\/)/, "").replace(/^\/?/, "/");
  return route === "/landing" ? "/" : route;
});
const routes = args.length > 0 ? args : ALL_ROUTES;
const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../data/ux-shots", stamp);
// 1440 = màn hình laptop rộng, 1024 = tablet ngang, 375 = điện thoại (design-system §12)
const WIDTHS = [1440, 1024, 375];

// Thang chữ chung (design-system §3) — cập nhật cùng lúc với bảng ở §3
const RULES = {
  scale: [12, 12.5, 13, 15, 17, 18, 20, 26, 28, 40, 56],
  // Cỡ fluid chỉ cho h1/h2 của landing (danh sách trắng X1): [min, max] px của clamp()
  display: { "display-1": [44, 76], "display-2": [32, 46] },
  // Số metric (tabular): miễn luật T4 — là dữ liệu, không phải chữ do tiêu đề dẫn
  metricSizes: [28, 56],
  // Vai của từng cấp heading theo tầng (tag landing lệch 1 cấp vì có tầng section display-2)
  roles: {
    app: { H1: ["page-title", 40], H2: ["block-title", 26], H3: ["section", 20], H4: ["box-title", 17] },
    landing: {
      H1: ["display-1", "display-1"],
      H2: ["display-2", "display-2"],
      H3: ["block-title", 26],
      H4: ["section", 20],
      H5: ["box-title", 17],
    },
  },
  // Cỡ của từng vai, xếp từ nông tới sâu (thứ tự dùng ở T5). Heading khai báo vai bằng `data-ux-role` khi tag
  // khác vai mặc định (VD hộp con "What to know" ngay dưới h2 là h3 nhưng mang vai box-title 17px — không nhảy
  // cấp). Không dùng để che heading sai cấp: vai sâu hơn heading ngay trước thì tag cũng phải sâu hơn (T5)
  roleSize: {
    "display-1": "display-1",
    "display-2": "display-2",
    "page-title": 40,
    "block-title": 26,
    section: 20,
    "box-title": 17,
  },
  // T5: vai cha hợp lệ của từng vai heading (cha = heading gần nhất phía trên có tag nông hơn). Không phụ thuộc
  // thứ tự anh em; bắt cả heading sai cấp lẫn `data-ux-role` dùng để che (design-system §3b T5)
  parents: {
    "display-1": [],
    "display-2": ["display-1"],
    "page-title": [],
    "block-title": ["page-title", "display-2"],
    section: ["block-title"],
    "box-title": ["block-title", "section"],
  },
  // Card / panel (bo góc tầng A 12px, panel landing 20px) — chung cho T6 và L2
  card: ".rounded-xl, .rounded-2xl, .rounded-\\[20px\\]",
  minTarget: 44, // C4: vùng chạm tối thiểu (design-system §12)
  cardHeadingChars: 200, // T6: card có hơn chừng này ký tự thì cần tiêu đề (ngưỡng biên tập, không phải đo)
};

// Đo trên trang đã render (chạy trong trình duyệt). Trả về vi phạm [máy], gợi ý [máy·gợi ý], bảng heading
function measure({ tier, rules }) {
  // Trình duyệt làm tròn subpixel (VD 12.5px có thể ra 12.48) — sai số cho phép khi so cỡ
  const near = (a, b) => Math.abs(a - b) < 0.3;
  const inScale = (size) => rules.scale.some((s) => near(size, s));
  const clip = (t) => (t ?? "").trim().replace(/\s+/g, " ").slice(0, 60);
  const where = (el) => `${el.tagName.toLowerCase()} "${clip(el.textContent)}"`;
  // Ẩn hẳn (display/visibility) → bỏ cả nhánh; khung ≤ 1px (sr-only, khung cao 0 chứa con absolute) chỉ loại
  // chính phần tử đó khỏi phép đo cỡ, con của nó vẫn được đo
  const shown = (el) => el.checkVisibility({ visibilityProperty: true });
  const sized = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const visible = (el) => shown(el) && sized(el);
  const level = (el) => (/^H[1-6]$/.test(el.tagName) ? Number(el.tagName[1]) : 0);
  const isMetric = (el, size) =>
    getComputedStyle(el).fontVariantNumeric.includes("tabular-nums") && rules.metricSizes.some((s) => near(size, s));
  const roles = rules.roles[tier];
  const violations = [];
  const warnings = [];
  // `key` = luật + vị trí, không chứa số đo (cỡ fluid, W×H, số chỗ đổi theo khổ) — dùng để gộp giữa 3 khổ
  const add = (list, rule, detail, key = `${rule}|${detail}`) => list.push({ rule, detail, key });

  // Các phần tử theo thứ tự đọc: heading + phần tử có chữ trực tiếp (kể cả <text> trong SVG biểu đồ)
  const SKIP = new Set(["SCRIPT", "STYLE", "TEMPLATE", "NOSCRIPT", "NEXTJS-PORTAL"]);
  const items = [];
  const faded = []; // nhánh opacity 0 (VD scroll reveal chưa chạy) — bỏ qua nhưng phải báo, không im lặng
  const walk = (el, inHeading) => {
    if (SKIP.has(el.tagName.toUpperCase()) || !shown(el)) return;
    if (getComputedStyle(el).opacity === "0") {
      if ((el.textContent ?? "").trim()) faded.push(where(el));
      return;
    }
    const lv = level(el);
    // Heading sr-only (khung ≤ 1px) vẫn thuộc outline (T5) nhưng không đo cỡ (T3/T4)
    if (lv) items.push({ el, heading: lv, measured: sized(el) });
    else if (!lv && !inHeading && sized(el) && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) {
      items.push({ el, heading: 0 });
    }
    for (const child of el.children) walk(child, inHeading || lv > 0);
  };
  walk(document.body, false);
  for (const it of items) it.size = parseFloat(getComputedStyle(it.el).fontSize);
  const measured = items.filter((it) => it.measured !== false);

  // T1 / T2: cỡ ngoài thang, chữ < 12px — gom theo cỡ để report đọc được
  const offScale = {};
  const fontSizes = {};
  for (const { el, heading, size } of measured) {
    fontSizes[`${size}px`] = (fontSizes[`${size}px`] ?? 0) + 1;
    if (el.closest("sub, sup")) continue; // chỉ số trong công thức (formula script 0.8em)
    if (tier === "landing" && (heading === 1 || heading === 2)) continue; // display fluid — kiểm ở T3
    if (inScale(size)) continue;
    const rule = size < 12 ? "T2" : "T1";
    const key = `${rule} ${size}px`;
    (offScale[key] ??= []).push(where(el));
  }
  for (const [key, els] of Object.entries(offScale)) {
    const [rule, size] = key.split(" ");
    add(violations, rule, `${size} ngoài thang §3 · ${els.length} chỗ · VD ${els.slice(0, 3).join(" | ")}`, key);
  }

  // T3: heading đúng cỡ của vai; T5: đúng 1 h1, không nhảy cấp
  const headings = [];
  const stack = []; // tổ tiên đang mở: { heading, role }
  let prev = 0;
  for (const { el, heading, measured: hasBox } of items) {
    if (!heading) continue;
    const cs = getComputedStyle(el);
    const size = parseFloat(cs.fontSize);
    const declared = el.dataset.uxRole;
    const own = (obj, k) => Object.prototype.hasOwnProperty.call(obj, k);
    const role = declared ? [declared, own(rules.roleSize, declared) ? rules.roleSize[declared] : null] : roles[`H${heading}`];
    headings.push({
      tag: `h${heading}`,
      role: role ? role[0] : "(không có vai)",
      size,
      weight: cs.fontWeight,
      color: cs.color,
      onDark: Boolean(el.closest(".on-dark")),
      measured: hasBox,
      text: clip(el.textContent),
    });
    const at = `T3|${where(el)}`;
    if (role && role[1] === null) {
      add(violations, "T3", `${where(el)}: data-ux-role="${role[0]}" không phải vai heading (§3b T5)`, at);
    } else if (!role) {
      add(violations, "T3", `${where(el)}: tầng ${tier} không dùng cấp h${heading}`, at);
    } else if (!hasBox) {
      // heading sr-only: không có cỡ nhìn thấy để so
    } else if (typeof role[1] === "string") {
      const [lo, hi] = rules.display[role[1]];
      if (size < lo - 0.3 || size > hi + 0.3) add(violations, "T3", `${where(el)}: ${size}px ngoài ${role[1]} [${lo}, ${hi}]`, at);
    } else if (!near(size, role[1])) {
      add(violations, "T3", `${where(el)}: ${size}px, vai ${role[0]} phải ${role[1]}px`, at);
    }
    if (prev && heading > prev + 1) {
      add(violations, "T5", `${where(el)}: nhảy cấp h${prev} → h${heading}`, `T5|skip|${where(el)}`);
    }
    prev = heading;
    // Cha = heading gần nhất phía trên có tag nông hơn; vai của nó phải nằm trong `parents` của vai này
    while (stack.length && stack[stack.length - 1].heading >= heading) stack.pop();
    const parent = stack[stack.length - 1];
    const allowed = role && own(rules.parents, role[0]) ? rules.parents[role[0]] : undefined;
    if (!parent && allowed?.length) {
      add(violations, "T5", `${where(el)}: vai ${role[0]} không có heading cha (cần ${allowed.join(", ")})`, `T5|parent|${where(el)}`);
    } else if (parent?.role && allowed && !allowed.includes(parent.role)) {
      add(
        violations,
        "T5",
        `${where(el)}: vai ${role[0]} nằm dưới vai ${parent.role} (h${parent.heading}) — cha hợp lệ: ${allowed.join(", ") || "không có"}`,
        `T5|parent|${where(el)}`,
      );
    }
    stack.push({ heading, role: role && own(rules.parents, role[0]) ? role[0] : null });
  }
  const h1Count = headings.filter((h) => h.tag === "h1").length;
  if (h1Count !== 1) add(violations, "T5", `trang có ${h1Count} thẻ h1 (phải đúng 1)`, "T5|h1-count");

  // T4: tiêu đề lớn hơn mọi chữ nó dẫn (tới heading cùng cấp hoặc cao hơn kế tiếp)
  measured.forEach(({ el, heading, size: own }, i) => {
    if (!heading) return;
    let max = 0;
    let biggest = null;
    for (let j = i + 1; j < measured.length; j++) {
      const next = measured[j];
      if (next.heading && next.heading <= heading) break;
      if (!next.heading && isMetric(next.el, next.size)) continue;
      if (next.size > max) [max, biggest] = [next.size, next.el];
    }
    if (biggest && max >= own - 0.3) {
      add(violations, "T4", `${where(el)} ${own}px ≤ chữ nó dẫn ${where(biggest)} ${max}px`, `T4|${where(el)}`);
    }
  });

  // T6 [gợi ý]: card nhiều chữ mà không có heading — chỉ báo card ngoài cùng
  const cards = [...document.body.querySelectorAll(rules.card)].filter(
    (c) => visible(c) && clip(c.innerText).length > 0 && (c.innerText ?? "").length > rules.cardHeadingChars,
  );
  for (const card of cards) {
    if (card.querySelector("h1, h2, h3, h4, h5, h6")) continue;
    if (cards.some((o) => o !== card && o.contains(card) && !o.querySelector("h1, h2, h3, h4, h5, h6"))) continue;
    add(warnings, "T6", `card không heading: "${clip(card.innerText)}"`, `T6|${clip(card.textContent)}`);
  }

  // L1: cuộn ngang toàn trang; L2 [gợi ý]: thanh cuộn lồng, chữ sát mép card
  const doc = document.documentElement;
  if (doc.scrollWidth > doc.clientWidth) {
    add(violations, "L1", `trang cuộn ngang: ${doc.scrollWidth} > ${doc.clientWidth}px`, "L1|page");
  }
  if (faded.length) {
    add(warnings, "meta", `${faded.length} nhánh opacity 0 không được đo bởi T1–T5 (reveal chưa chạy?) · VD ${faded.slice(0, 3).join(" | ")}`, "meta|faded");
  }
  for (const el of document.querySelectorAll("main *")) {
    const cs = getComputedStyle(el);
    const scrollY = /(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 2;
    const scrollX = /(auto|scroll)/.test(cs.overflowX) && el.scrollWidth > el.clientWidth + 2;
    if (scrollY || scrollX) {
      const name = `${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 3).join(".")}`;
      add(warnings, "L2", `thanh cuộn lồng ${name} ${scrollY ? "↕" : ""}${scrollX ? "↔" : ""} (${el.scrollWidth}×${el.scrollHeight} in ${el.clientWidth}×${el.clientHeight})`, `L2|scroll|${name}`);
    }
  }
  for (const { el } of measured) {
    const card = el.closest(rules.card);
    if (!card) continue;
    const r = el.getBoundingClientRect();
    const c = card.getBoundingClientRect();
    const gap = Math.min(r.left - c.left, c.right - r.right);
    if (gap < 12) add(warnings, "L2", `${where(el)} cách mép card ${Math.round(gap)}px`, `L2|edge|${where(el)}`);
  }

  // C4: vùng chạm = khung của chính phần tử bấm được (vùng nới bằng ::before hay padding của cha không tính)
  const targets = document.querySelectorAll(
    'body button, body [role="button"], body [role="tab"], body [role="slider"], body [role="switch"], body summary, body select',
  );
  for (const el of targets) {
    if (!visible(el) || el.closest("nextjs-portal")) continue;
    const r = el.getBoundingClientRect();
    if (r.width < rules.minTarget - 0.5 || r.height < rules.minTarget - 0.5) {
      add(violations, "C4", `${where(el)}: vùng chạm ${Math.round(r.width)}×${Math.round(r.height)}px < ${rules.minTarget}`, `C4|${where(el)}`);
    }
  }

  return { violations, warnings, headings, fontSizes };
}

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL ?? "msedge" });
const report = {};
for (const route of routes) {
  const tier = route === "/" ? "landing" : "app";
  const slug = route.replace(/\W+/g, "_").replace(/^_|_$/g, "") || "landing";
  const dir = path.join(ROOT, slug);
  mkdirSync(dir, { recursive: true });
  const entry = { tier, files: [], consoleErrors: [], checks: {} };
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => entry.consoleErrors.push(`${width}px: ${e}`));
    page.on("console", (m) => m.type() === "error" && entry.consoleErrors.push(`${width}px: ${m.text()}`));
    await page.goto(BASE_URL + route, { waitUntil: "networkidle", timeout: 120_000 });
    await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
    await page.waitForTimeout(1200);
    for (const state of ["as-loaded", "expanded"]) {
      if (state === "expanded") {
        // Bấm lần lượt nút ĐẦU TIÊN còn đóng: danh sách `.all()` gom 1 lần bị lệch chỉ số sau mỗi
        // lần bấm (nút vừa mở rời khỏi bộ chọn) nên bỏ sót nút (ux-reviewer 2026-10-29)
        // Chỉ nút trong <main>: nút dev-tools của Next (đã ẩn ở trên) cũng có aria-expanded, bấm vào nút
        // ẩn thì chờ hết timeout mỗi lần — vòng lặp treo hàng chục phút
        const closed = page.locator('main button[aria-expanded="false"]');
        for (let guard = 0; guard < 50; guard++) {
          const before = await closed.count();
          if (before === 0) break;
          await closed.first().click({ timeout: 3000 }).catch(() => {});
          await page.waitForTimeout(100);
          if ((await closed.count()) >= before) break; // nút không mở được — dừng, không bấm lại 50 lần
        }
        await page.waitForTimeout(400);
      }
      // Chromium không chụp quá 16,384px một ảnh (phần sau lặp lại đầu trang) — trang dài hơn thì chụp
      // thành nhiều phần `-full-partN.png` (ux-reviewer 2026-10-29)
      const height = await page.evaluate(() => document.documentElement.scrollHeight);
      const SLICE = 12_000;
      if (height <= 16_000) {
        const full = path.join(dir, `${width}-${state}-full.png`);
        await page.screenshot({ path: full, fullPage: true });
        entry.files.push(full);
      } else {
        for (let y = 0, part = 1; y < height; y += SLICE, part++) {
          const file = path.join(dir, `${width}-${state}-full-part${part}.png`);
          await page.screenshot({ path: file, fullPage: true, clip: { x: 0, y, width, height: Math.min(SLICE, height - y) } });
          entry.files.push(file);
        }
      }
      if (width === WIDTHS[0]) {
        const blocks = await page.locator("main > div > *, main > section").all();
        let i = 1;
        for (const block of blocks) {
          const file = path.join(dir, `${width}-${state}-block${String(i).padStart(2, "0")}.png`);
          await block.screenshot({ path: file }).catch(() => {});
          entry.files.push(file);
          i++;
        }
      }
    }
    // Máy đo ở trạng thái đã mở hết
    const checks = await page.evaluate(measure, { tier, rules: RULES });
    // A1: axe-core theo WCAG 2.x A/AA — serious/critical là vi phạm, mức nhẹ hơn là gợi ý
    const axe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .exclude("nextjs-portal")
      .analyze()
      .catch((e) => ({ error: String(e), violations: [] }));
    if (axe.error) checks.warnings.push({ rule: "A1", detail: `axe-core không chạy được: ${axe.error}`, key: "A1|error" });
    for (const v of axe.violations) {
      const list = v.impact === "serious" || v.impact === "critical" ? checks.violations : checks.warnings;
      const targets = v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ");
      list.push({ rule: "A1", detail: `axe ${v.id} (${v.impact}) · ${v.nodes.length} chỗ · ${v.help} · VD ${targets}`, key: `A1|${v.id}` });
    }
    entry.checks[width] = checks;
    await ctx.close();
  }
  report[route] = entry;
}
await browser.close();

// T3 giữa các trang: cùng vai phải cùng cỡ, độ đậm, màu (đo ở khổ rộng nhất). Vai display chỉ có ở landing.
// Trên dải tối (X2, `.on-dark`) màu chữ khác là được phép — chỉ so cỡ + độ đậm
const roleTable = {};
const shape = {}; // vai → các cặp cỡ + độ đậm (mọi nền)
const tone = {}; // vai → các màu trên nền sáng
for (const [route, e] of Object.entries(report)) {
  for (const h of e.checks[WIDTHS[0]]?.headings ?? []) {
    // heading không vai / vai lạ đã báo T3 trong trang; heading sr-only không có cỡ nhìn thấy
    if (!Object.prototype.hasOwnProperty.call(RULES.roleSize, h.role) || h.measured === false) continue;
    const style = `${h.size}px w${h.weight} ${h.onDark ? "on-dark" : h.color}`;
    ((roleTable[h.role] ??= {})[style] ??= new Set()).add(route);
    (shape[h.role] ??= new Set()).add(`${h.size}|${h.weight}`);
    if (!h.onDark) (tone[h.role] ??= new Set()).add(h.color);
  }
}
const crossRoute = [];
for (const [role, styles] of Object.entries(roleTable)) {
  if (shape[role].size > 1 || (tone[role]?.size ?? 0) > 1) {
    const detail = Object.entries(styles).map(([s, rs]) => `${s} ở ${[...rs].join(", ")}`).join(" ≠ ");
    crossRoute.push({ rule: "T3", detail: `vai ${role} khác kiểu giữa các trang (hoặc trong 1 trang): ${detail}`, key: `T3|cross|${role}` });
  }
}
const roleSummary = Object.fromEntries(
  Object.entries(roleTable).map(([role, styles]) => [role, Object.fromEntries(Object.entries(styles).map(([s, rs]) => [s, [...rs]]))]),
);

mkdirSync(ROOT, { recursive: true });
writeFileSync(path.join(ROOT, "report.json"), JSON.stringify({ routes: report, roleTable: roleSummary, crossRoute }, null, 2));
console.log(`Ảnh + report.json: ${ROOT}`);
// Đếm lỗi riêng: cùng `key` (luật + vị trí) ở nhiều khổ màn hình chỉ tính 1 lần
let total = crossRoute.length;
for (const [route, e] of Object.entries(report)) {
  const unique = new Map();
  const warns = new Set();
  for (const c of Object.values(e.checks)) {
    for (const v of c.violations) unique.set(v.key, v.rule);
    for (const w of c.warnings) warns.add(w.key);
  }
  const byRule = {};
  for (const rule of unique.values()) byRule[rule] = (byRule[rule] ?? 0) + 1;
  total += unique.size;
  const rules = Object.entries(byRule).map(([r, k]) => `${r}×${k}`).join(" ") || "—";
  console.log(`${route}: ${e.files.length} ảnh · lỗi console ${e.consoleErrors.length} · vi phạm ${unique.size} (${rules}) · gợi ý ${warns.size}`);
}
if (crossRoute.length) console.log(`Giữa các trang (T3): ${crossRoute.length} vai khác kiểu`);
console.log(`UX gate (máy): ${total === 0 ? "PASS" : `FAIL · ${total} vi phạm riêng (gộp 3 khổ)`} — chi tiết trong report.json`);
