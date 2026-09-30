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

const PAGES = {
  landing: "/",
  overview: "/overview",
  analytics: "/analytics",
  topics: "/topics",
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

for (const [name, route] of targets) {
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
  await page.screenshot({ path: file, fullPage: true });
  console.log(`✓ ${name} → ${path.relative(process.cwd(), file)}`);
}

await browser.close();
if (failures.length > 0) {
  console.error(`\nKhông chụp (giữ ảnh cũ):\n  ${failures.join("\n  ")}`);
  console.error("Kiểm tra backend :8000 đang chạy và src/dashboard/.env.local trỏ về http://localhost:8000");
  process.exit(1);
}
