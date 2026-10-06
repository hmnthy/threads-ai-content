# Brand assets — Unthreaded (logo "Unknot")

> **Trạng thái**: logo và animation đã được Thy duyệt ngày 2026-10-01. **Chưa có ADR** — ghi bằng `/record-decision` trước khi đưa vào UI.
> **Nguồn duy nhất của file logo**: `src/dashboard/public/brand/` (Next.js phục vụ tại `/brand/*`). Không tạo bản sao ở nơi khác, trừ `app/icon.svg` (bắt buộc theo quy ước Next).

## File

| File | Nội dung | viewBox | Dùng cho |
|---|---|---|---|
| `unthreaded-mark.svg` | Mark: nút ba lá (trefoil) + đuôi amber | 48 × 48 | Avatar, nguồn để tạo `app/icon.svg` |
| `unthreaded-lockup.svg` | Mark + chữ "Unthreaded" (IBM Plex Sans 500, đã chuyển thành path) | 179.43 × 48 | Navbar, README, mọi nơi tĩnh |
| `unthreaded-lockup-tagline.svg` | Lockup + "The algorithm, read back to you." | 190.05 × 48 | Topbar tầng A (logo + tagline) |
| `unthreaded-lockup-animated-once.svg` | Bản động, chạy 1 lần rồi dừng ở logo tĩnh | 179.4 × 48 | Navbar / landing khi tải trang |
| `unthreaded-lockup-animated.svg` | Bản động lặp (chu kỳ ~6,55 s) | 179.4 × 48 | Chỉ dùng ở hero/trang trình diễn, không dùng ở navbar |

## Quy tắc

- **Không sửa tay** hình học hay màu trong các file này. Muốn đổi → quay lại vòng thiết kế, sinh lại file.
- Màu: mực `#111827` (= `--text-primary`), amber `#B45309` (= `--amber-600`), nền sáng. Chỉ có phiên bản cho light mode (design-system §0).
- Chữ trong lockup đã là path — không phụ thuộc font máy người xem.
- Các file chứa một khối metadata C2PA (`xmlns:c2pa`) do môi trường xuất file gắn vào — không ảnh hưởng hiển thị, không cần xoá.

## Animation

- Kịch bản: logo tĩnh 1,2 s → nút siết nhẹ lấy đà → bung ra, 3 chỗ bắt chéo được tháo liên tiếp (~0,5 s) → sợi lượn một khúc xuống dưới dòng chữ, lướt sang phải, mờ ở mép phải → logo hiện lại.
- Kỹ thuật: 64 khung vector (30 fps) từ mô phỏng sợi chỉ mềm; chuyển khung bằng CSS keyframes bên trong SVG → **chạy được khi nhúng qua `<img>`**, không cần JS.
- `prefers-reduced-motion: reduce` được xử lý bên trong SVG (chỉ hiện logo tĩnh) — đã kiểm khi SVG nhúng inline. Với `<img>`, dùng `<picture>` để chắc chắn:

```tsx
<picture>
  <source media="(prefers-reduced-motion: reduce)" srcSet="/brand/unthreaded-lockup.svg" />
  <img src="/brand/unthreaded-lockup-animated-once.svg" alt="Unthreaded" width={179} height={48} />
</picture>
```

- Dung lượng: ~400 KB mỗi file động (~35 KB khi server nén gzip). Không nhúng vào email/PDF; dùng bản tĩnh.
- Mới kiểm trên Chromium; chưa kiểm Safari/Firefox.

## Việc còn lại (cho Claude Code)

1. `/record-decision "Logo Unknot và vị trí asset thương hiệu"` → `/decision-sweep` (luật cấm placeholder "@" cũ trong `Nav.tsx`, `LandingNav.tsx`).
2. Tạo `src/dashboard/src/components/BrandLogo.tsx` (dùng `<picture>` như trên), thay chữ "@" trong `Nav.tsx` và `LandingNav.tsx`.
3. Tạo `src/dashboard/src/app/icon.svg` từ `unthreaded-mark.svg`; xoá `app/favicon.ico` mặc định của create-next-app.
4. Thêm mục Brand vào `docs/claude/design-system.md` trỏ về file này; thêm test kiểm `app/icon.svg` khớp `unthreaded-mark.svg`.
5. `npm run lint`, `npm run typecheck`, `npm run build`, xem navbar thật → `/checkpoint` → `/design-sync` nếu cần đẩy lên Claude Design.
