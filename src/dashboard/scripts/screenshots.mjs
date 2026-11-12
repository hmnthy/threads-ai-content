// Chụp lại ảnh cho README (docs/screenshots/*.png) — cùng khung nhìn mỗi lần để ảnh so được.
// Cần: backend (uvicorn src.main:app --port 8000) + `npm run dev` đang chạy.
// Dùng Edge có sẵn trên Windows (channel "msedge") — không tải Chromium riêng.
//
//   npm run screenshots                  # chụp cả 4 trang
//   npm run screenshots -- overview      # chỉ 1 trang
//   BASE_URL=http://localhost:3001 npm run screenshots
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const OUT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../docs/screenshots");

// Ảnh README hiện có rộng 1740px = khung nhìn 1160 × tỉ lệ điểm ảnh 1.5
const VIEWPORT = { width: 1160, height: 900 };
const DEVICE_SCALE_FACTOR = 1.5;
// Chromium vẽ 1 ảnh tối đa 16 384 px mỗi chiều (giới hạn texture GPU) — chừa 384 px an toàn
const MAX_CAPTURE_PX = 16_000;

// `maxHeight` (px CSS) chỉ đặt cho từng trang cụ thể — không áp chung (ảnh landing cần đủ trang). /topics
// dài ~15 000 px → ảnh 5,6 MB; chỉ chụp phần đầu đại diện (đầu trang, khối 01–02).
const PAGES = {
  landing: { route: "/" },
  overview: { route: "/overview" },
  analytics: { route: "/analytics" },
  topics: { route: "/topics", maxHeight: 3600 },
  // Trang dài (chữ đoạn nguồn 2 thứ tiếng) → chỉ phần đầu: đầu trang, khối 01, đầu khối 02 (ADR-0037)
  "rag-pipeline": { route: "/rag-pipeline", maxHeight: 3600 },
};

const only = process.argv.slice(2);
const targets = Object.entries(PAGES).filter(([name]) => only.length === 0 || only.includes(name));
if (targets.length === 0) {
  console.error(`Không có trang nào khớp ${only.join(", ")}. Có: ${Object.keys(PAGES).join(", ")}`);
  process.exit(1);
}

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL ?? "msedge" });
const context = await browser.newContext({
  viewport: VIEWPORT,
  deviceScaleFactor: DEVICE_SCALE_FACTOR,
  colorScheme: "light",
  reducedMotion: "reduce", // tắt animation để ảnh không chụp giữa chừng hiệu ứng
});
const page = await context.newPage();
const failures = [];

for (const [name, { route }] of targets) {
  const url = BASE_URL + route;
  const apiErrors = [];
  page.removeAllListeners("response");
  page.on("response", (res) => {
    if (res.url().includes(":8000") && res.status() >= 400) apiErrors.push(`${res.status()} ${res.url()}`);
  });
  const res = await page.goto(url, { waitUntil: "networkidle", timeout: 60_000 });
  // Trang tool gọi API phía client: không được chụp khi đang hiện lỗi "Could not reach the API"
  const apiDown = await page.getByText("Could not reach the API").count();
  if (!res?.ok() || apiDown > 0 || apiErrors.length > 0) {
    failures.push(`${name}: HTTP ${res?.status()}${apiDown ? ", API không kết nối được" : ""} ${apiErrors.join(" ")}`);
    continue;
  }
  // Ẩn biểu tượng dev của Next.js ("N" góc trái dưới) — không phải UI của sản phẩm
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  // Ảnh lazy-load (VD ảnh tác giả) chỉ tải khi cuộn tới — cuộn hết trang rồi chờ ảnh xong
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight / 2) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
    await Promise.all(
      [...document.images].map((img) =>
        img.complete ? null : new Promise((r) => img.addEventListener("load", r, { once: true })),
      ),
    );
  });
  await page.waitForLoadState("networkidle");
  const file = path.join(OUT_DIR, `${name}.png`);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const maxHeight = PAGES[name].maxHeight;
  const shotHeight = maxHeight && height > maxHeight ? maxHeight : height;
  if (shotHeight * DEVICE_SCALE_FACTOR <= MAX_CAPTURE_PX) {
    await page.screenshot(
      shotHeight < height
        ? { path: file, fullPage: true, clip: { x: 0, y: 0, width: VIEWPORT.width, height: shotHeight } }
        : { path: file, fullPage: true },
    );
  } else {
    // Ảnh quá giới hạn của Chromium thì phần vượt bị vẽ lại từ đầu trang (landing 2026-11-01: ~12 200 px CSS
    // × 1.5 = 18 248 px) → chụp từng đoạn rồi ghép bằng sharp. sharp chỉ là phụ thuộc TUỲ CHỌN của next nên nạp
    // muộn ở đây: thiếu sharp thì chỉ trang quá dài lỗi, các trang khác vẫn chụp được (code-reviewer)
    const { default: sharp } = await import("sharp");
    const step = Math.floor(MAX_CAPTURE_PX / DEVICE_SCALE_FACTOR);
    const parts = [];
    for (let y = 0; y < shotHeight; y += step) {
      const h = Math.min(step, shotHeight - y);
      const buf = await page.screenshot({ fullPage: true, clip: { x: 0, y, width: VIEWPORT.width, height: h } });
      parts.push({ input: buf, top: Math.round(y * DEVICE_SCALE_FACTOR), left: 0 });
    }
    const width = Math.round(VIEWPORT.width * DEVICE_SCALE_FACTOR);
    await sharp({
      create: { width, height: Math.round(shotHeight * DEVICE_SCALE_FACTOR), channels: 4, background: "#ffffff" },
      limitInputPixels: false,
    })
      .composite(parts)
      .png()
      .toFile(file);
  }
  console.log(`✓ ${name} → ${path.relative(process.cwd(), file)}`);
}

await browser.close();
if (failures.length > 0) {
  console.error(`\nKhông chụp (giữ ảnh cũ):\n  ${failures.join("\n  ")}`);
  console.error("Kiểm tra backend :8000 đang chạy và src/dashboard/.env.local trỏ về http://localhost:8000");
  process.exit(1);
}
