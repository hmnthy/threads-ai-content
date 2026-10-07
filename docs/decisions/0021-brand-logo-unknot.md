# ADR-0021: Dùng logo Unknot từ một nguồn file duy nhất, ở vị trí cố định cho từng chỗ hiển thị

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-07
- **Người quyết**: Thy (duyệt logo + animation 2026-10-01; chốt vị trí và hướng "logo + port landing" 2026-10-07); vị trí theo mockup landing của Claude Design

## Bối cảnh

- Logo "Unknot" (nút ba lá + đuôi amber) và animation tháo nút đã được Thy duyệt 2026-10-01, nhập repo ở PR #3: 5 file SVG
  trong `src/dashboard/public/brand/` (`docs/design/brand-assets.md`). Hai bản động ~400 KB mỗi file (~35 KB khi gzip),
  chuyển khung bằng CSS keyframes bên trong SVG nên chạy được qua `<img>`, không cần JS.
- Code vẫn dùng chữ "@" trong vòng tròn amber làm logo giữ chỗ ở cả hai navbar (`Nav.tsx`, `LandingNav.tsx`) và favicon
  mặc định của create-next-app (`src/dashboard/src/app/favicon.ico`).
- Mockup landing (`src/dashboard/mockups/landing.dc.html`) và `docs/design/landing-handoff.md` §3.1, §3.7 đã định vị trí:
  navbar lockup tĩnh 28px, hero lockup động lặp 64px (chỉ ở đây), khối CTA mark 52px, footer lockup 24px.
- `brand-assets.md` ghi rõ "Chưa có ADR — ghi trước khi đưa vào UI".

## Quyết định

1. **Một nguồn file**: mọi logo lấy từ `src/dashboard/public/brand/`, không sửa tay hình học hay màu; bản sao duy nhất được
   phép là `src/dashboard/src/app/icon.svg` (favicon, giống hệt `unthreaded-mark.svg` từng byte). `favicon.ico` bị xoá.
2. **Một component**: `src/dashboard/src/components/BrandLogo.tsx` với 3 biến thể `lockup` (tĩnh), `lockup-animated`
   (lặp), `mark`. Biến thể động luôn bọc `<picture>`: người xem bật `prefers-reduced-motion` thì nhận bản tĩnh.
3. **Vị trí**: navbar landing = lockup tĩnh 28px; hero landing = lockup động lặp 64px (chỗ duy nhất có chuyển động);
   khối CTA = mark 52px; footer landing = lockup 24px; topbar dashboard = lockup tĩnh 28px + tagline giữ dạng chữ HTML,
   không chuyển động. Hero, CTA, footer áp khi port landing mới (nhánh kế tiếp); navbar và favicon áp ngay.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Bản động chạy 1 lần ở navbar (gợi ý trong `brand-assets.md`) | Có chuyển động khi tải mọi trang | Navbar dashboard animate mỗi lần chuyển trang — gây phân tâm khi đọc số | Mockup đặt chuyển động duy nhất ở hero landing |
| `next/image` cho logo | Tối ưu ảnh tự động | Không tối ưu được SVG (phải bật `dangerouslyAllowSVG` hoặc `unoptimized`), file vector không lợi gì; SVG động cần phục vụ nguyên bản | Dùng `<img>` + `<picture>` (có chú thích ESLint) |
| Lockup kèm tagline dạng path (`unthreaded-lockup-tagline.svg`) ở topbar | Một file | Tagline ở cỡ 28px quá nhỏ để đọc; chữ trong path không chọn/không đọc được bằng trình đọc màn hình | Tagline giữ chữ HTML |

## Hệ quả

- Code: `BrandLogo.tsx` mới (prop `alt`: `""` khi logo chỉ trang trí, VD khối CTA); `Nav.tsx`, `LandingNav.tsx` dùng
  lockup; `app/icon.svg` mới, `favicon.ico` xoá. Test: `tests/test_branding.py` (favicon giống hệt mark, hai navbar
  dùng `BrandLogo`, `test_brand_assets_are_not_hand_edited` giữ dấu SHA-256 của 5 file logo).
- Docs: `docs/design/brand-assets.md` (trạng thái, việc còn lại), mục Brand trong `docs/claude/design-system.md`,
  `docs/design/ui-contract.md`.
- Luật: `ADR0021-placeholder-logo` (logo giữ chỗ — chữ "@" hoặc icon "at" — trong code dashboard và mockup); `[[stale_asset]]` 4 ảnh README (navbar
  đổi ở mọi trang). Bỏ `BrandLogo.tsx`, `app/icon.svg` khỏi `planned_paths`.
- **Rủi ro chấp nhận**: animation mới kiểm trên Chromium; Safari/Firefox chưa kiểm. Nếu trình duyệt không chạy keyframes
  trong SVG qua `<img>`, người xem thấy khung đầu (logo tĩnh) — không vỡ trang. Chỉ có bản light mode (design-system §0);
  favicon SVG không có bản dự phòng `.ico` (trình duyệt cũ / crawler gọi `/favicon.ico` nhận 404) và nét xám đậm khó
  thấy trên thanh tab nền tối của trình duyệt.
- **Xem lại khi**: deploy công khai (kiểm Safari/Firefox, đo thời gian tải hero với file ~400 KB, cân nhắc favicon có nền
  hoặc `icon.png` dự phòng — nhờ Claude Design xuất); hoặc có dark mode; hoặc
  thương hiệu đổi (quay lại vòng thiết kế, sinh lại file, không sửa tay).

### Hệ quả UI

- Thêm: `UI-0021-logo-placement`, `UI-0021-reduced-motion`, `UI-0021-favicon`, `UI-0021-assets-untouched`.
- Sửa: `UI-0009-display-name` (logo hai navbar giờ là lockup có `alt="Unthreaded"`; số dòng mới).
