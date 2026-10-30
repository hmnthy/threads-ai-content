# ADR-0029: Một thang chữ và một sổ luật UI/UX cho mọi trang, kiểm bằng reviewer + máy đo

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-30
- **Người quyết**: Thy (nêu vấn đề landing và /topics khác chuẩn, chọn 3 phương án qua câu hỏi 2026-10-30: một thang
  chung, cưỡng chế 2 lớp không chặn commit, 2 PR tách bạch); nội dung sổ luật và máy đo do Claude đề xuất

## Bối cảnh

- Thy so landing với /topics: landing do một phiên dựng, /topics do phiên khác dựng, nên mỗi trang theo một bộ luật
  riêng. Trên /topics tiêu đề lớn, khối rõ, mạch đọc rõ; trên landing tiêu đề khối rất bé, khó quan sát.
- Nguyên nhân trong tài liệu: thang chặt "tiêu đề luôn lớn hơn nội dung nó dẫn" (Thy chốt 2026-10-29) ở
  `docs/claude/design-system.md` §3 chỉ ghi cho trang app tầng A. Landing chỉ có 1 dòng ở §7 ("câu hỏi panel 13px w600
  amber → câu trả lời 24px"), và `@agent-ux-reviewer` chỉ chấm theo luật tầng A, mỗi lần 1 trang.
- Bằng chứng trong code (2026-10-30):
  - tiêu đề panel Proof của landing là `<span>` 13px, nhỏ hơn chữ nó dẫn ngay dưới — câu trả lời 24px
    (`src/dashboard/src/components/LandingProof.tsx:239` → `:242`), 17px (`:1219` → `:1220`);
  - toàn dashboard dùng khoảng 21 cỡ chữ khác nhau (10 → 76px), nhiều cặp sát nhau (11/11.5, 13/13.5, 14/14.5);
  - các trang app cũng lệch nhau: tiêu đề trang Analytics 24px, Topics 40px; tiêu đề khối Overview 20px (một khối
    15px), Topics 26px; landing có 3 cỡ tiêu đề section (38 / 46 / 52px).
- Máy đo dựng trong đợt này (`src/dashboard/scripts/ux-shots.mjs`), chạy trên bản live
  `unthreaded-analytics.vercel.app` 2026-10-30: 63 vi phạm máy (landing 27, overview 15, analytics 14, topics 4, cộng 3
  vi phạm T3 giữa các trang). /topics gần đạt nhất, nên thang của nó được lấy làm chuẩn.

## Quyết định

1. **Một thang chữ cho toàn sản phẩm** (`docs/claude/design-system.md` §3): mỗi cỡ một vai, tập cỡ hợp lệ 12 · 12.5 ·
   13 · 15 · 17 · 18 · 20 · 26 · 28 · 40 · 56px. Landing chỉ thêm 2 bậc trưng bày fluid ở đỉnh thang: display-1 (H1
   hero, `clamp(44px, 6.4vw, 76px)`) và display-2 (tiêu đề section, `clamp(32px, 3.6vw, 46px)`). Cùng vai thì cùng cỡ,
   độ đậm, màu trên mọi trang; tag tiêu đề của landing lệch 1 cấp (tiêu đề khối landing là `h3` 26px).
2. **Một sổ luật có mã** (§3b): T chữ, L bố cục, C khối và mạch đọc, N số và công thức, B người đọc và ngôn ngữ, A tiếp
   cận (WCAG 2.2 AA), X danh sách trắng những điểm landing được phép khác (X1–X6). Không có trong danh sách trắng thì
   landing theo luật chung.
3. **Cưỡng chế 2 lớp, không chặn commit**:
   - `@agent-ux-reviewer` luôn chấm mọi trang, trích mã luật ở mỗi lỗi, lập bảng vai × trang, so xu hướng với lần chạy
     trước;
   - máy đo trong `ux-shots.mjs` (mặc định mọi route) đo luật [máy] trên trang đã render: cỡ ngoài thang, tiêu đề sai
     cỡ theo vai, tiêu đề nhỏ hơn chữ nó dẫn, cấp tiêu đề và vai cha, vùng chạm, axe-core WCAG A/AA.

   Còn ≥ 1 vi phạm máy thì UX gate FAIL; reviewer không được hạ.
4. Sửa các trang cho đạt sổ luật là **PR riêng** sau PR này; Thy duyệt bố cục landing mới ở PR đó.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Landing giữ thang riêng, chỉ buộc "tiêu đề lớn hơn nội dung" + tiêu đề khối ≥ 20px | Linh hoạt cho trang marketing | Hai trang vẫn khác "giọng"; mỗi phiên lại tự chọn cỡ | Thy chọn một thang chung |
| 3 lớp: thêm cổng pre-commit chặn cỡ chữ ngoài thang trong code | Lỗi mới bị chặn ngay lúc commit | Phải sửa ~100 chỗ cũ trước khi bật; thêm một cổng chặn | Thy chọn 2 lớp, không chặn commit |
| Chỉ viết lại luật cho reviewer, không máy đo | Nhanh nhất | Vẫn dựa vào phán đoán bằng mắt nên dễ lệch giữa các phiên — đúng lỗi vừa xảy ra | Không giải quyết gốc |
| Gộp luật + sửa trang trong 1 PR | Ít bước | PR rất lớn; Thy phải duyệt luật và giao diện cùng lúc | Thy chọn 2 PR |

## Hệ quả

- Docs: `docs/claude/design-system.md` §3 (bảng vai), §3b (sổ luật), §6, §7, §12, §13; `docs/design/landing-handoff.md`
  (cỡ chữ landing theo thang chung); `docs/design/ui-contract-audit.md`. Harness: `.claude/agents/ux-reviewer.md`
  (chấm mọi trang, mã luật, máy đo không thương lượng), `.claude/rules/dashboard.md` (một sổ luật cho mọi trang) —
  commit riêng vào kho harness (ADR-0027).
- Code: `src/dashboard/scripts/ux-shots.mjs` (máy đo, `RULES` phải khớp bảng §3); devDependency
  `@axe-core/playwright` (MPL-2.0, chỉ dùng lúc phát triển, không vào bản deploy).
- Luật: `ADR0029-landing-own-scale` cấm các câu cũ cho landing một thang riêng (câu hỏi panel 13px, câu trả lời 24px,
  eyebrow 13px ở cả §7 lẫn handoff, H2 CTA 52px) và cỡ cũ ngoài thang ở §6 (header bảng 11px, tiêu đề hàng 14px). Không có luật chặn cỡ
  chữ trong code: Thy chọn không chặn commit, máy đo + reviewer giữ phần đó.
- **Nợ chấp nhận**: các trang hiện tại vi phạm (63 vi phạm máy); thang ở 2 nơi (§3 và `RULES` trong script) chỉ giữ
  khớp bằng comment và review. Một số luật vẫn chấm bằng mắt (L3–L5, C1–C3, N, B) nên còn phụ thuộc reviewer.
- **Xem lại khi**: PR sửa trang xong mà vi phạm máy quay lại ở các PR UI sau (khi đó cân nhắc bật cổng chặn commit,
  phương án 3 lớp); có trang mới (thêm vào `ALL_ROUTES`); hoặc có dark mode / thương hiệu đổi.

### Hệ quả UI

- Thêm: `UI-0029-type-scale` (một thang chữ, mỗi cỡ một vai, landing chỉ thêm display-1/2), `UI-0029-heading-roles`
  (tiêu đề là heading thật theo bảng vai, cha hợp lệ, `data-ux-role`), `UI-0029-landing-whitelist` (X1–X6).
- Sửa chữ (không đổi ràng buộc): `UI-0023-page-questions` cột E "không tiêu đề cỡ landing" → "không dùng
  display-1/2 của landing", vì tiêu đề khối landing nay cùng 26px với trang app.
- Nâng mốc "Cập nhật tới: ADR-0029" của `docs/design/ui-contract.md`.
