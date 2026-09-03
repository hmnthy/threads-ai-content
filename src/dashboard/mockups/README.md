# Dashboard mockups

Design system hiện hành: **v3.1 Amber** → đã merge vào [`docs/claude/design-system.md`](../../../docs/claude/design-system.md) (2026-09-03). Đó là nguồn sự thật duy nhất — không còn bản copy `design-system-v3.1-amber.md` ở đây.

| File | Nội dung |
|---|---|
| `design-system.dc.html` | Style guide xem được: swatch có hex, type specimen, gallery component, sơ đồ layout, khối Author |
| `overview-amber.dc.html` | **Hướng chốt.** Overview + timeline brush chạy thật |
| `overview-cyan.dc.html` | Hướng không chọn, giữ để đối chiếu |
| `threads-dashboard.dc.html` | Bản violet cũ, 3 tab (Overview / Analytics / Topic Explorer) — chưa chuyển sang amber |
| `threads-dashboard.html` | Bản standalone offline của file trên |
| `photo-author.jpg` | Ảnh tác giả dùng trong mockup |

## Mở thế nào

Mở trực tiếp bằng browser. Cần mạng để tải Inter, IBM Plex Mono và Phosphor Icons.
`overview-amber.dc.html` là bản tương tác: kéo timeline để thấy mọi chỉ số đổi theo.

## Chưa làm

- Tab Analytics và Topic Explorer chưa chuyển sang amber (vẫn đang ở bản violet).
- Tầng B landing page chưa dựng; mới có khối Author trong style guide.
- Số liệu per-post là mô phỏng, nhưng tính qua đúng công thức trong `src/analysis/`. Các số đã verify thật được giữ nguyên: 135 content unit, 1.423 follower có country data (71,5% VN / 19,3% FR, 2026-08-31), noise 3%, min_cluster_size 5.

## Với Next.js app

`globals.css` và `AnalyticsOverview.tsx` đã refactor sang token v3.1 (2026-09-03) — bỏ zebra striping, bỏ gradient bar ngoài hero, bỏ hex hardcode. **Chưa làm**: `Nav.tsx`, `TopicExplorer.tsx`, `topics/page.tsx` vẫn dùng token v2 cũ (có alias sang giá trị amber trong `globals.css` để không vỡ layout, nhưng chưa refactor cấu trúc/component theo `design-system.md` §5–§6 — timeline brush, KPI strip phẳng...). Tầng B landing page chưa dựng, chỉ có khối Author trong style guide.
