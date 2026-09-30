---
paths:
  - "src/dashboard/**"
---

# Dashboard (Next.js 16) — design routing bắt buộc

- **Đọc `docs/claude/design-system.md` (v3.1 Amber) trước dòng UI đầu tiên** — kể cả mockup nhanh, artifact, HTML demo. Đây là nguồn sự thật DUY NHẤT về design.
- Thứ tự thắng khi mâu thuẫn: `design-system.md` > `docs/design/dashboard-reference.png` (chỉ cấu trúc/hình khối, **không** màu) > mọi nguồn khác.
- Không tự chọn palette/font/layout, không dùng palette mặc định của model. Icon: Phosphor.
- Tra cứu UX/chart: skill `ui-lookup` (CLI `tools/ui-ux-pro-max/scripts/search.py`). **Không** nạp SKILL.md của tool đó; **cấm** `--design-system` và `--persist`. Query theo triệu chứng quan sát được, 2–5 từ (cookbook: `design-system.md` §11).
- Mockup `.dc.html` là spec cho layout/tương tác; **không bao giờ** là nguồn methodology (VD công thức KPI lấy từ backend, không tính lại ở client).
- Copy UI tiếng Anh 100%. Không hiển thị nguyên văn bình luận của follower.
- Next.js 16 có breaking changes so với kiến thức cũ — đọc `src/dashboard/AGENTS.md` và `node_modules/next/dist/docs/`, hoặc MCP `context7`.
- Xong việc UI: `npm run lint` + `npx tsc --noEmit` + `npm run build` sạch, và xem thật trước khi báo "done" (trình duyệt, hoặc `npm run screenshots` rồi mở ảnh).
