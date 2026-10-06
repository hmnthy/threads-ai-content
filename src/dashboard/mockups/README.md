# Dashboard mockups

Design system hiện hành: **v3.2 Amber** — nguồn sự thật duy nhất là [`docs/claude/design-system.md`](../../../docs/claude/design-system.md). Mockup chỉ quyết định design, không quyết định methodology.

| File | Nội dung |
|---|---|
| `landing.dc.html` | **Landing tầng B đã chốt (2026-10-01).** Spec port: [`docs/design/landing-handoff.md`](../../../docs/design/landing-handoff.md) |
| `design-system.dc.html` | Style guide xem được: swatch, type specimen, gallery component, khối Author |
| `overview-amber.dc.html` | Hướng chốt cho app (tầng A). Overview + timeline brush chạy thật |
| `overview-cyan.dc.html` | Hướng không chọn, giữ để đối chiếu (design-system §1) |
| `photo-author.jpg` | Ảnh tác giả dùng trong mockup |
| `support.js` | Runtime của file `.dc.html` — không sửa tay |

## Mở thế nào

Mở trực tiếp bằng browser (cần mạng để tải Inter, IBM Plex Mono). `landing.dc.html` dùng logo ở `../public/brand/`.
Trong landing: toggle Channel/Topic ở hero, rê chuột hàng chủ đề, chọn cụm ở panel NLP, bấm node trong sơ đồ, nút "Method and limits".

## Số liệu

Số trong `landing.dc.html` lấy từ `data/threads.db` snapshot 2026-10-01: 150 root post, 144 đo được (6 loại vì views = 0, ADR-0011), 1.369 reply tác giả (353/674/342, ADR-0004), 9 cụm, nhiễu 36,1%, `validity_index` 0,317, median engagement 1,99%. Panel CMI là số **sơ bộ** tính cho mockup (xấp xỉ chuẩn, chưa phải RQ-04) — không port số đó vào code.

## Đã xoá (2026-10-01)

`threads-dashboard.dc.html` + `threads-dashboard.html` (violet, tab Generate Content trái ADR-0001, số cũ 135 unit), `design-system-v3.1-amber.md` (đã merge 2026-09-03).
