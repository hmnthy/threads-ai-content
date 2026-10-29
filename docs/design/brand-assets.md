# Brand assets — Unthreaded (logo "Unknot")

> **Trạng thái**: logo và animation đã được Thy duyệt ngày 2026-10-01; vị trí dùng chốt ở **ADR-0021** (2026-10-07), cỡ topbar và nhịp hoạt cảnh ở **ADR-0026** (2026-10-29).
> **Nguồn duy nhất của file logo**: `src/dashboard/public/brand/` (Next.js phục vụ tại `/brand/*`). Không tạo bản sao ở nơi khác, trừ `app/icon.svg` (bắt buộc theo quy ước Next).

## File

| File | Nội dung | viewBox | Dùng cho |
|---|---|---|---|
| `unthreaded-mark.svg` | Mark: nút ba lá (trefoil) + đuôi amber | 48 × 48 | Avatar, nguồn để tạo `app/icon.svg` |
| `unthreaded-lockup.svg` | Mark + chữ "Unthreaded" (IBM Plex Sans 500, đã chuyển thành path) | 179.43 × 48 | Footer landing 24px, bản dự phòng khi giảm chuyển động, README |
| `unthreaded-lockup-tagline.svg` | Lockup + "The algorithm, read back to you." | 190.05 × 48 | Không dùng ở topbar (ADR-0021: tagline giữ chữ HTML — chữ trong path nhỏ, không đọc được bằng trình đọc màn hình); dự phòng |
| `unthreaded-lockup-animated-once.svg` | Bản động, chạy 1 lần rồi dừng ở logo tĩnh | 179.4 × 48 | Topbar dashboard 36px, navbar landing 28px, hero landing 64px — phát lại mỗi 15 giây (`lockup-replay`, ADR-0026) |
| `unthreaded-lockup-animated.svg` | Bản động lặp (chu kỳ ~6,55 s) | 179.4 × 48 | Không còn dùng từ ADR-0026 (hero chuyển sang phát lại mỗi 15 giây); giữ làm dự phòng |

## Quy tắc

- **Không sửa tay** hình học hay màu trong các file này. Muốn đổi → quay lại vòng thiết kế, sinh lại file.
- Màu: mực `#111827` (= `--text-primary`), amber `#B45309` (= `--amber-600`), nền sáng. Chỉ có phiên bản cho light mode (design-system §0).
- Chữ trong lockup đã là path — không phụ thuộc font máy người xem.
- Các file chứa một khối metadata C2PA (`xmlns:c2pa`) do môi trường xuất file gắn vào — không ảnh hưởng hiển thị, không cần xoá.

## Animation

- Kịch bản: logo tĩnh 1,2 s → nút siết nhẹ lấy đà → bung ra, 3 chỗ bắt chéo được tháo liên tiếp (~0,5 s) → sợi lượn một khúc xuống dưới dòng chữ, lướt sang phải, mờ ở mép phải → logo hiện lại.
- Kỹ thuật: 64 khung vector (30 fps) từ mô phỏng sợi chỉ mềm; chuyển khung bằng CSS keyframes bên trong SVG → **chạy được khi nhúng qua `<img>`**, không cần JS.
- `prefers-reduced-motion: reduce` được xử lý bên trong SVG (chỉ hiện logo tĩnh) — đã kiểm khi SVG nhúng inline.
- Phát lại mỗi 15 giây (ADR-0026, `src/dashboard/src/components/BrandLogoReplay.tsx`): tải
  `unthreaded-lockup-animated-once.svg` 1 lần thành Blob, mỗi chu kỳ tạo object URL mới cho `<img>` → hoạt cảnh chạy
  lại từ khung đầu, không tải mạng lại; người xem bật giảm chuyển động chỉ nhận bản tĩnh, không hẹn giờ.

```tsx
// Code thật (src/dashboard/src/components/BrandLogo.tsx)
<BrandLogo variant="lockup-replay" height={36} />
```

- Dung lượng: ~400 KB mỗi file động (~35 KB khi server nén gzip). Không nhúng vào email/PDF; dùng bản tĩnh.
- Mới kiểm trên Chromium; chưa kiểm Safari/Firefox. Trình duyệt headless không vẽ khung động của SVG trong `<img>` khi chụp ảnh — kiểm bằng mắt.

## Đã làm (ADR-0021, 2026-10-07)

- `src/dashboard/src/components/BrandLogo.tsx` (`lockup` / `lockup-replay` / `mark`, cùng `lockup-animated` không còn dùng); hai navbar và hero dùng `lockup-replay` (ADR-0026), thay chữ "@" giữ chỗ (luật `ADR0021-placeholder-logo`).
- `src/dashboard/src/app/icon.svg` = bản sao của `unthreaded-mark.svg` (test `test_favicon_is_the_unknot_mark_byte_for_byte`); `favicon.ico` đã xoá.
- Mục 10b trong `docs/claude/design-system.md`.

Còn lại: kiểm Safari/Firefox khi deploy.
