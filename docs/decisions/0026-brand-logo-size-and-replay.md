# ADR-0026: Logo topbar 36px kèm tagline 15px, hoạt cảnh logo phát lại mỗi 15 giây

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-29
- **Người quyết**: Thy (yêu cầu logo + tagline lớn hơn và hoạt cảnh mỗi 15 giây, chọn phạm vi "cả hai" qua câu hỏi
  2026-10-29); cách làm kỹ thuật đề xuất bởi Claude, Thy duyệt bố cục sau khi xem trang

## Bối cảnh

- ADR-0021 mục 3 chốt: topbar dashboard = lockup **tĩnh 28px**, tagline chữ HTML bên dưới, **không chuyển động**; hero
  landing = lockup động **lặp liên tục** (chỗ duy nhất có chuyển động); navbar landing = lockup tĩnh 28px.
- Khi duyệt trang /topics dựng lại (2026-10-29), Thy yêu cầu: "để nhìn professional hơn thì logo và tagline cũng nên lớn
  hơn so với kích thước hiện tại" (tagline lúc đó 12px dưới logo 28px), rồi "Cập nhật cho logo animation chạy mỗi 15s".
  Khi được hỏi logo nào, Thy chọn **cả hai**: thanh trên cùng (app + navbar landing) và hero landing.
- File có sẵn từ PR #3: `unthreaded-lockup-animated-once.svg` — hoạt cảnh tháo nút 6.553 s, `animation-fill-mode:
  both`, dừng ở khung cuối = logo hoàn chỉnh; bản lặp `unthreaded-lockup-animated.svg` cùng nhịp, `infinite`. Test
  `test_brand_assets_are_not_hand_edited` giữ SHA-256 cả 5 file (ADR-0021 mục 1: không sửa tay).
- SVG trong `<img>` chạy CSS keyframes của chính tài liệu SVG; gắn lại cùng URL không bảo đảm chạy lại từ đầu (trình
  duyệt dùng chung bản đã giải mã).

## Quyết định

1. **Topbar dashboard**: lockup **36px**, tagline "The algorithm, read back to you." **15px** đặt cạnh logo, ngăn bằng
   vạch dọc mảnh; dưới 640px chỉ giữ logo (tagline ẩn để logo và nút tài khoản cùng một hàng).
2. **Hoạt cảnh**: topbar dashboard, navbar landing (28px) và hero landing (64px) dùng biến thể `lockup-replay` của
   `BrandLogo` — bản "chạy 1 lần" phát lúc mở trang rồi **mỗi 15 giây** phát lại, giữa hai lần đứng ở logo hoàn chỉnh.
   Phát lại bằng cách tải file 1 lần thành Blob và tạo object URL mới mỗi chu kỳ (tài liệu SVG mới → hoạt cảnh chạy lại
   từ khung đầu, không tải mạng lần nữa). `prefers-reduced-motion: reduce` → chỉ logo tĩnh, không hẹn giờ.
3. Phần còn lại của ADR-0021 giữ nguyên: một nguồn file `public/brand/`, một component `BrandLogo`, không sửa tay file
   logo, favicon `app/icon.svg`, khối CTA mark 52px, footer landing lockup tĩnh 24px.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Chỉ topbar phát lại, hero giữ lặp liên tục | Hero không đổi | Hai nhịp chuyển động khác nhau trên cùng landing | Thy chọn "cả hai" |
| Chỉ hero phát lại mỗi 15 giây, topbar tĩnh | Giữ đúng ADR-0021 cho topbar | Không đáp ứng yêu cầu logo topbar sống động hơn | Thy chọn "cả hai" |
| Gắn lại `<img>` cùng URL mỗi 15 giây | Đơn giản | Không bảo đảm hoạt cảnh chạy lại (bản giải mã dùng chung) | Không tin cậy |
| Thêm `?r=<n>` vào URL mỗi chu kỳ | Chắc chạy lại | Tải lại ~400 KB mỗi 15 giây | Tốn băng thông vô ích |
| Sửa SVG thêm khoảng nghỉ 8.4 s vào keyframes, đặt `infinite` | Không cần JS | Sửa tay file logo — cấm ở ADR-0021 mục 1, phá dấu SHA-256 | Trái ADR-0021 |
| Blob + object URL mới mỗi chu kỳ (chọn) | Chạy lại chắc chắn, tải 1 lần, không sửa file | Cần JS phía client; phải thu hồi URL cũ | — |

## Hệ quả

- Code: `src/dashboard/src/components/BrandLogoReplay.tsx` (mới), `BrandLogo.tsx` (biến thể `lockup-replay`),
  `Nav.tsx`, `LandingNav.tsx`, `LandingHero.tsx`. Biến thể `lockup-animated` (lặp liên tục) không còn chỗ dùng; file
  `unthreaded-lockup-animated.svg` giữ nguyên trong `public/brand/` (không xoá asset đã duyệt).
- Test: `test_navbars_render_the_brand_logo` kiểm hai navbar + hero dùng `<BrandLogo variant="lockup-replay"`.
- Docs: `docs/design/brand-assets.md`, mục Brand trong `docs/claude/design-system.md`, `docs/design/ui-contract.md`.
- Luật: `ADR0026-loop-logo` cấm dùng lại bản lặp liên tục (`variant="lockup-animated"`) trong code dashboard;
  `ADR0026-static-topbar-claim` cấm câu cũ "chuyển động chỉ ở hero" trong docs/rules; `[[stale_asset]]` 3 ảnh README
  trang app (topbar đổi). Sửa chữ `fix` của `ADR0021-placeholder-logo` cho đúng cỡ mới.
- **Rủi ro chấp nhận**: hoạt cảnh SVG trong `<img>` không chụp được bằng trình duyệt tự động (headless không vẽ khung
  động, kể cả file gốc) — chỉ kiểm được việc đổi URL mỗi 15 giây; mắt thường kiểm trên Edge/Chrome. Safari/Firefox
  chưa kiểm (như ADR-0021). Chuyển động định kỳ ở topbar có thể làm phân tâm khi đọc số — đổi lại, 15 giây là khoảng
  nghỉ đủ dài và người cần có thể bật giảm chuyển động (áp cả khi bật giữa phiên). WCAG 2.2.2 (mức A) đòi
  cách dừng cho chuyển động tự chạy quá 5 giây song song nội dung — trang chưa có nút dừng riêng, chỉ dựa vào
  cài đặt giảm chuyển động; tab ẩn thì không phát.
- **Xem lại khi**: có phản hồi người xem rằng chuyển động gây phân tâm trên trang dashboard; hoặc deploy công khai
  (đo thời gian tải ~400 KB bản once ở topbar mọi trang); hoặc có dark mode / thương hiệu đổi (theo ADR-0021).

### Hệ quả UI

- Thêm: `UI-0026-logo-replay` (topbar 36px + tagline 15px, nhịp phát lại 15 giây).
- Sửa: `UI-0021-logo-placement` (topbar 36px + tagline 15px cạnh logo; topbar, navbar landing, hero dùng
  `lockup-replay`), `UI-0021-reduced-motion` (áp cho `lockup-replay`, không còn "chỉ hero"), `UI-0009-tagline`
  (vị trí tagline topbar, ẩn dưới 640px).
- Nâng mốc "Cập nhật tới: ADR-0026" của `docs/design/ui-contract.md`.
