// Chụp 1 trang cho @agent-ux-reviewer: toàn trang ở 3 khổ + từng khối của <main> ở khổ rộng, ở 2 trạng
// thái (như người xem thấy lúc mở trang / mọi khối thu gọn đã mở). Kèm số đo tự động: cuộn ngang, thanh
// cuộn lồng, chữ sát mép card, các cỡ chữ đang dùng. Ảnh lưu ở data/ux-shots/ (gitignored, riêng tư).
// Cần `npm run dev` đang chạy (hoặc BASE_URL trỏ server khác).
//
//   node scripts/ux-shots.mjs topics            (route không cần "/"; "landing" = "/")
//   BASE_URL=http://localhost:3100 node scripts/ux-shots.mjs topics analytics
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
// Git Bash đổi "/topics" thành "C:/Program Files/Git/topics" (MSYS path conversion) — bỏ phần đó
const routes = process.argv.slice(2).map((arg) => {
  const route = arg.replace(/^[A-Za-z]:\/.*?\/Git(?=\/)/, "").replace(/^\/?/, "/");
  return route === "/landing" ? "/" : route;
});
if (routes.length === 0) {
  console.error("Cần ít nhất 1 route, VD: node scripts/ux-shots.mjs topics");
  process.exit(1);
}
const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../data/ux-shots", stamp);
// 1440 = màn hình laptop rộng, 1024 = tablet ngang, 375 = điện thoại (design-system §12)
const WIDTHS = [1440, 1024, 375];

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL ?? "msedge" });
const report = {};
for (const route of routes) {
  const slug = route.replace(/\W+/g, "_").replace(/^_|_$/g, "") || "landing";
  const dir = path.join(ROOT, slug);
  mkdirSync(dir, { recursive: true });
  const entry = { files: [], consoleErrors: [], checks: {} };
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
    // Số đo tự động ở trạng thái đã mở hết
    entry.checks[width] = await page.evaluate(() => {
      const doc = document.documentElement;
      const nestedScroll = [];
      const tightEdges = [];
      const fontSizes = {};
      for (const el of document.querySelectorAll("main *")) {
        const cs = getComputedStyle(el);
        const scrollY = /(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 2;
        const scrollX = /(auto|scroll)/.test(cs.overflowX) && el.scrollWidth > el.clientWidth + 2;
        if (scrollY || scrollX) {
          nestedScroll.push(`${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 3).join(".")} ${scrollY ? "↕" : ""}${scrollX ? "↔" : ""} (${el.scrollWidth}×${el.scrollHeight} in ${el.clientWidth}×${el.clientHeight})`);
        }
        if (el.childElementCount === 0 && el.textContent.trim()) {
          const size = cs.fontSize;
          fontSizes[size] = (fontSizes[size] ?? 0) + 1;
          const card = el.closest(".rounded-xl, .rounded-\\[20px\\]");
          if (card) {
            const r = el.getBoundingClientRect();
            const c = card.getBoundingClientRect();
            const gap = Math.min(r.left - c.left, c.right - r.right);
            if (r.width > 0 && gap < 12) tightEdges.push(`"${el.textContent.trim().slice(0, 40)}" ${Math.round(gap)}px from card edge`);
          }
        }
      }
      return {
        horizontalPageScroll: doc.scrollWidth > doc.clientWidth,
        nestedScroll: nestedScroll.slice(0, 20),
        tightEdges: tightEdges.slice(0, 20),
        fontSizes,
      };
    });
    await ctx.close();
  }
  report[route] = entry;
}
await browser.close();
mkdirSync(ROOT, { recursive: true });
writeFileSync(path.join(ROOT, "report.json"), JSON.stringify(report, null, 2));
console.log(`Ảnh + report.json: ${ROOT}`);
for (const [route, e] of Object.entries(report)) {
  console.log(`${route}: ${e.files.length} ảnh · lỗi console ${e.consoleErrors.length}`);
}
