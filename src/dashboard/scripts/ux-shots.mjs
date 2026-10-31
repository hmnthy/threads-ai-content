// Chụp trang cho @agent-ux-reviewer: toàn trang ở 3 khổ + từng khối của <main> ở khổ rộng, ở 2 trạng thái
// (như người xem thấy lúc mở trang / mọi khối thu gọn đã mở). Kèm máy đo theo sổ luật UI/UX
// (docs/claude/design-system.md §3b; máy đo luật [máy] thuộc T/L/C/K/A, còn N/B/X do reviewer chấm):
// `violations` = luật [máy], còn ≥ 1 thì UX gate FAIL;
// `warnings` = luật [máy·gợi ý], reviewer xác nhận trên ảnh. Ảnh + report.json lưu ở data/ux-shots/
// (gitignored, riêng tư). Cần `npm run dev` đang chạy (hoặc BASE_URL trỏ server khác).
//
//   node scripts/ux-shots.mjs                   (không đối số = mọi trang: so "cùng vai cùng kiểu" giữa trang, T3)
//   node scripts/ux-shots.mjs topics            (route không cần "/"; "landing" = "/")
//   BASE_URL=http://localhost:3100 node scripts/ux-shots.mjs topics analytics
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";
import { mkdirSync, realpathSync, writeFileSync } from "node:fs";
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
export const RULES = {
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
  // K1–K3: hộp Key numbers (design-system §3b K, ADR-0030). Hộp số = nền ấm chứa danh sách <dl>
  keyNumbers: {
    box: ".bg-warm-surface",
    title: "Key numbers",
    maxItems: 4, // K2: nhiều hơn thì dùng bảng (ngưỡng biên tập)
    value: 28, // K2: số chính = vai metric
    label: 15, // K2: nhãn dưới số = body w600
    rhythm: 4, // K3: khoảng giữa các dòng lệch nhau tối đa (px) — sai số làm tròn, không phải khoảng thiết kế
    slack: 8, // K3: đáy hộp cách dòng cuối tối đa padding + chừng này px — quá thì hộp bị kéo giãn
  },
};

// Đo trên trang đã render (chạy trong trình duyệt). Trả về vi phạm [máy], gợi ý [máy·gợi ý], bảng heading
export function measure({ tier, rules }) {
  // Đo từ đầu trang: bấm mở nút / chụp từng khối làm trang cuộn, mà toạ độ phần tử sticky đổi theo vị trí cuộn (K3)
  window.scrollTo({ top: 0, left: 0, behavior: "instant" });
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

  // K1–K3: hộp Key numbers — một component, một tên (K1); số 28px tabular w700 căn trái trên dòng riêng, nhãn
  // 15px w600 ngay dưới (K2); hộp cao theo nội dung, dính khi đứng ở cột phụ (K3)
  const kn = rules.keyNumbers;
  const px = (v) => parseFloat(v) || 0;
  // Khung của chính đoạn chữ (không phải khung khối rộng hết dòng) — bắt cả số căn phải bằng text-align
  const textBox = (el) => {
    const range = document.createRange();
    range.selectNodeContents(el);
    return range.getBoundingClientRect();
  };
  const bounds = (els) => {
    const rs = els.map((el) => el.getBoundingClientRect());
    return { top: Math.min(...rs.map((r) => r.top)), bottom: Math.max(...rs.map((r) => r.bottom)), left: Math.min(...rs.map((r) => r.left)) };
  };
  // Hộp số: phần tử khai data-ux, cộng khung nền ấm GẦN NHẤT của mỗi <dl> (khung nền ấm bọc ngoài không tính)
  const found = new Set([
    ...document.querySelectorAll('[data-ux="key-numbers"]'),
    ...[...document.querySelectorAll("dl")].map((d) => d.closest(kn.box)).filter(Boolean),
  ]);
  // Lồng nhau: phần tử khai data-ux thắng (khung nền ấm bên trong nó bị bỏ); không ai khai thì giữ khung trong cùng
  const marked = (el) => el.dataset.ux === "key-numbers";
  const boxes = [...found].filter((box) => {
    if (!visible(box) || !box.querySelector("dl")) return false;
    const others = [...found].filter((o) => o !== box);
    if (others.some((o) => marked(o) && o.contains(box))) return false;
    return marked(box) || !others.some((o) => box.contains(o));
  });
  for (const box of boxes) {
    const title = box.querySelector("h1, h2, h3, h4, h5, h6");
    const list = box.querySelector("dl");
    // Dòng = phần tử con bọc (div) của <dl>, hoặc cặp <dt> + các <dd> theo sau khi <dl> không bọc
    const rows = [];
    for (const kid of [...list.children].filter(sized)) {
      if (kid.tagName === "DD" && rows.length && rows[rows.length - 1][0].tagName === "DT") rows[rows.length - 1].push(kid);
      else rows.push([kid]);
    }
    const inRow = (row, el) => row.some((part) => part.contains(el));
    const pick = (row) => {
      const texts = measured.filter((m) => !m.heading && inRow(row, m.el));
      const value = texts.find((m) => m.el.closest('[data-ux="kn-value"]')) ?? texts[0];
      const label =
        texts.find((m) => m.el.closest('[data-ux="kn-label"]')) ?? texts.find((m) => value && m !== value && !value.el.contains(m.el));
      return { value, label };
    };
    // Khoá theo chữ (tiêu đề khối chứa hộp + tiêu đề hộp + nhãn dòng đầu), không theo số thứ tự: một hộp ẩn ở một khổ
    // không làm trượt khoá của các hộp khác
    const block = clip(box.closest("section")?.querySelector("h1, h2, h3")?.textContent);
    const firstLabel = rows.length ? clip(pick(rows[0]).label?.el.textContent) : "";
    const id = `${block}|${clip(title?.textContent)}|${firstLabel}`;
    const name = `hộp số "${clip(title?.textContent ?? box.textContent)}" (khối "${block}")`;
    if (box.dataset.ux !== "key-numbers") {
      add(violations, "K1", `${name}: không dùng component KeyNumbers (thiếu data-ux="key-numbers")`, `K1|component|${id}`);
    }
    if (clip(title?.textContent) !== kn.title) {
      add(violations, "K1", `${name}: tiêu đề phải đúng "${kn.title}" (phạm vi ghi ở dòng nhãn phía trên)`, `K1|title|${id}`);
    }
    if (rows.length > kn.maxItems) add(violations, "K2", `${name}: ${rows.length} số > ${kn.maxItems} (dùng bảng)`, `K2|count|${id}`);
    for (const row of rows) {
      const { value, label } = pick(row);
      if (!value) continue;
      const vs = getComputedStyle(value.el);
      const rv = textBox(value.el);
      const problems = [];
      if (!near(value.size, kn.value) || !vs.fontVariantNumeric.includes("tabular-nums") || Number(vs.fontWeight) < 700) {
        problems.push(`chữ đầu dòng ${value.size}px w${vs.fontWeight} — số chính phải ${kn.value}px tabular w700`);
      }
      if (rv.left - bounds(row).left > 2) problems.push("số không căn trái");
      if (label) {
        const labelStyle = getComputedStyle(label.el);
        const rt = textBox(label.el);
        if (rt.bottom <= rv.top + 2) problems.push("nhãn nằm trên số — số đứng trước, nhãn ngay dưới");
        else if (rt.top < rv.bottom - 2) problems.push("nhãn cùng dòng với số — số phải đứng riêng một dòng");
        if (!near(label.size, kn.label) || Number(labelStyle.fontWeight) < 600) {
          problems.push(`nhãn ${label.size}px w${labelStyle.fontWeight} — phải ${kn.label}px w600`);
        }
      }
      const rowId = clip(label?.el.textContent ?? value.el.textContent);
      if (problems.length) add(violations, "K2", `${name} · "${clip(value.el.textContent)}": ${problems.join("; ")}`, `K2|row|${id}|${rowId}`);
    }
    // K3: không rải khoảng thừa (justify space-*, dòng flex-grow), nhịp đều, hộp và danh sách không cao hơn nội dung
    const ls = getComputedStyle(list);
    const grown = rows.some((row) => row.some((part) => px(getComputedStyle(part).flexGrow) > 0));
    if (/space-/.test(ls.justifyContent) || grown) {
      const how = grown ? "dòng có flex-grow" : `justify-content: ${ls.justifyContent}`;
      add(violations, "K3", `${name}: danh sách rải khoảng thừa giữa các dòng (${how})`, `K3|spread|${id}`);
    }
    const rects = rows.map(bounds);
    const gaps = rects.slice(1).map((rect, i) => rect.top - rects[i].bottom);
    if (gaps.length > 1 && Math.max(...gaps) - Math.min(...gaps) > kn.rhythm) {
      add(violations, "K3", `${name}: khoảng giữa các dòng lệch nhau ${gaps.map(Math.round).join(" / ")}px`, `K3|rhythm|${id}`);
    }
    // Khung = khung nền ấm chứa danh sách (data-ux có thể nằm ở phần tử bọc ngoài khung — đo khung, không đo phần bọc)
    const inner = list.closest(kn.box);
    const frame = inner && box.contains(inner) ? inner : box;
    const bs = getComputedStyle(frame);
    const rb = frame.getBoundingClientRect();
    // Đáy nội dung = đáy thấp nhất của chữ trong khung và của dòng cuối (thanh tỉ lệ K4 không có chữ) — không lấy con
    // trực tiếp: phần tử bọc flex-1 lấp tới đáy khung. Không đo được chữ nào (reveal chưa chạy, đã báo meta|faded) → bỏ qua
    const inside = measured.filter((m) => frame.contains(m.el)).map((m) => m.el.getBoundingClientRect().bottom);
    const content = inside.length ? Math.max(...inside, ...(rects.length ? [rects[rects.length - 1].bottom] : [])) : null;
    // Đáy tự nhiên của khung (khi không bị kéo giãn) — dùng ở K3 để biết hàng có gì cao hơn hộp không
    const naturalBottom = content === null ? rb.bottom : content + px(bs.paddingBottom) + px(bs.borderBottomWidth);
    if (content !== null) {
      const boxSlack = rb.bottom - px(bs.paddingBottom) - px(bs.borderBottomWidth) - content;
      const rl = list.getBoundingClientRect();
      const listSlack = rects.length ? rl.bottom - px(ls.paddingBottom) - rects[rects.length - 1].bottom : 0;
      const slack = Math.max(boxSlack, listSlack);
      if (slack > kn.slack) {
        add(violations, "K3", `${name}: hộp cao hơn nội dung ${Math.round(slack)}px (bị kéo giãn theo cột bên cạnh)`, `K3|stretch|${id}`);
      }
    }
    // Ở cột phụ → phải dính khi cuộn. Đi lên từ khung tới lưới gần nhất có ≥ 2 cột (bỏ qua lưới 1 cột xếp chồng); cột
    // phụ = ô hẹp hơn ô rộng nhất CÙNG HÀNG (ô col-span ở hàng khác không tính). Theo cơ chế CSS của sticky:
    // - CẦN dính khi hàng có thứ cao hơn đáy tự nhiên của hộp (hộp cao nhất hàng thì không có gì để cuộn qua);
    // - DÍNH ĐƯỢC khi khung hoặc phần tử bọc nó có `sticky` + `top`, CÒN CHỖ TRỐNG BÊN DƯỚI nó trong khối chứa (khối
    //   chứa của ô lưới là cả lưới, của phần tử khác là cha nó — nằm sát đáy thì không trượt được dù thấp hơn khối
    //   chứa), và không tổ tiên nào có overflow khác visible/clip (sticky bám vào khung cuộn đó, không dính theo trang);
    // - ô lưới tự dính trượt trong cả lưới, không chỉ trong hàng: lưới còn ô nằm dưới hộp (VD `below` của AnswerRow)
    //   thì hộp trượt đè lên ô đó → `K3|sticky-overlap`.
    // Xếp chồng 1 cột (màn hình hẹp) thì không cần dính
    const columns = (s) => s.gridTemplateColumns.replace(/\[[^\]]*\]/g, " ").trim().split(/\s+/).length;
    const chain = [];
    let cell = null;
    for (let el = frame; el && el.tagName !== "SECTION" && el !== document.body; el = el.parentElement) {
      chain.push(el);
      const ps = el.parentElement ? getComputedStyle(el.parentElement) : null;
      if (ps && /grid/.test(ps.display) && columns(ps) > 1) {
        cell = el;
        break;
      }
    }
    if (cell) {
      const rc = cell.getBoundingClientRect();
      const siblings = [...cell.parentElement.children].filter((c) => c !== cell && sized(c));
      const others = siblings.map((c) => c.getBoundingClientRect());
      const inRowOf = (r) => r.top < rc.bottom - 1 && r.bottom > rc.top + 1;
      const sameRow = others.filter(inRowOf);
      const side = rc.width < Math.max(rc.width, ...sameRow.map((r) => r.width)) - 1;
      // Cần dính khi một ô khác cùng hàng có đáy TỰ NHIÊN thấp hơn đáy tự nhiên của hộp. Lưới kéo giãn mọi ô theo hàng
      // (và kéo giãn lan xuống con qua flex, h-full, flex-1), nên đo ô bên cạnh ở trạng thái không kéo giãn: tạm đặt
      // align-self:start rồi trả lại ngay (cùng tác vụ, trang không vẽ lại). Phần thân của chính ô (chú thích dưới
      // khung, padding) không phải thứ để cuộn qua
      const contentBottom = (el) => {
        const prev = el.style.alignSelf;
        el.style.alignSelf = "start";
        const bottom = el.getBoundingClientRect().bottom;
        el.style.alignSelf = prev;
        return bottom;
      };
      const need = siblings.some((c) => inRowOf(c.getBoundingClientRect()) && contentBottom(c) > naturalBottom + 1);
      const clipped = (el) => {
        for (let a = el.parentElement; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
          const s = getComputedStyle(a);
          if (!/^(visible|clip)$/.test(s.overflowX) || !/^(visible|clip)$/.test(s.overflowY)) return true;
        }
        return false;
      };
      // Còn chỗ trống dưới phần tử trong content box của khối chứa (cha; ô lưới thì cha chính là lưới)
      const roomBelow = (el) => {
        const p = el.parentElement;
        const ps = getComputedStyle(p);
        const floor = p.getBoundingClientRect().bottom - px(ps.paddingBottom) - px(ps.borderBottomWidth);
        // Trình duyệt giới hạn sticky theo margin box của phần tử, không theo khung viền
        return el.getBoundingClientRect().bottom + px(getComputedStyle(el).marginBottom) < floor - 1;
      };
      const sticks = (el) => {
        const s = getComputedStyle(el);
        return s.position === "sticky" && s.top !== "auto" && roomBelow(el) && !clipped(el);
      };
      const stuck = chain.some(sticks);
      if (side && need && !stuck) {
        add(violations, "K3", `${name}: ở cột phụ nhưng không dính khi cuộn (cần sticky + top + self-start)`, `K3|sticky|${id}`);
      }
      // Chỉ ô lưới tự dính mới trượt trong cả lưới; phần tử dính bên trong ô chỉ trượt trong ô (hàng của nó)
      const cellSticky = sticks(cell);
      const under = others.filter((r) => r.top >= rc.bottom - 1 && r.left < rc.right - 1 && r.right > rc.left + 1);
      if (cellSticky && under.length) {
        add(violations, "K3", `${name}: hộp dính nằm chung lưới với khối bên dưới — cuộn sẽ trượt đè lên khối đó`, `K3|sticky-overlap|${id}`);
      }
    }
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

// Chạy trực tiếp (`node scripts/ux-shots.mjs`) mới chụp + đo; import thì chỉ lấy RULES + measure, để kiểm máy đo trên
// trang mẫu dựng tay (mỗi luật [máy]: một bố cục đúng phải qua, một bố cục sai phải bị bắt)
// So đường dẫn thật (realpath): chạy qua symlink/junction vẫn nhận ra, không im lặng thoát
if (process.argv[1] && realpathSync.native(fileURLToPath(import.meta.url)) === realpathSync.native(process.argv[1])) {
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
}
