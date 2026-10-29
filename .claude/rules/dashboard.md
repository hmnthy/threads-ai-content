---
paths:
  - "src/dashboard/**"
---

# Dashboard (Next.js 16) — design routing bắt buộc

- **Đọc `docs/claude/design-system.md` (v3.2 Amber) trước dòng UI đầu tiên** — kể cả mockup nhanh, artifact, HTML demo. Đây là nguồn sự thật DUY NHẤT về design.
- **Trước khi port mockup / đổi cấu trúc UI: đọc `docs/design/ui-contract.md`** (ADR-0020) — cột A–D là ràng buộc kỹ thuật (trường thật, điều code làm), thắng mockup khi lệch; chỗ lệch đã biết ở `docs/design/ui-contract-audit.md`. Copy mockup sai sự thật kỹ thuật → port theo hợp đồng, ghi vào PR.
- Thứ tự thắng khi mâu thuẫn: `design-system.md` > `docs/design/dashboard-reference.png` (chỉ cấu trúc/hình khối, **không** màu) > mọi nguồn khác.
- Không tự chọn palette/font/layout, không dùng palette mặc định của model. Icon: Phosphor.
- Tra cứu UX/chart: skill `ui-lookup` (CLI `tools/ui-ux-pro-max/scripts/search.py`). **Không** nạp SKILL.md của tool đó; **cấm** `--design-system` và `--persist`. Query theo triệu chứng quan sát được, 2–5 từ (cookbook: `design-system.md` §11).
- Mockup `.dc.html` là spec cho layout/tương tác; **không bao giờ** là nguồn methodology (VD công thức KPI lấy từ backend, không tính lại ở client).
- `DistributionStats` từ API có `n === 0` → hiện "—", không vẽ median/IQR (backend trả 0.0 cho tập rỗng) — ở **mọi** chỗ đọc cùng giá trị, cả ghi chú hover, `aria-label`, `aria-live`. Kiểm "có dữ liệu" trên số (`> 0`), không trên chuỗi đã định dạng. % làm tròn floor/ceil: nhân số nguyên trước khi chia (`Math.floor(a * 100 / b)`), không `Math.floor(a / b * 100)` (sai số dấu phẩy động). Khối phân phối có toggle đổi tập so sánh phải báo `excluded_no_views` của đúng tập đang vẽ. Câu sinh tự động: "highest/lowest" trên tập con phải nêu tập con; so với median phải có nhánh bằng nhau; không dùng `|| <số>` làm số thay data.
- Đổi chữ hiển thị (copy) → chạy `@agent-copy-reviewer` trên chữ đã render (thuật ngữ/mẫu số định nghĩa trước khi dùng, một câu một ý, không nói quá dữ liệu); Thy duyệt câu cuối, ghi vào `docs/design/ui-contract-audit.md` để mockup theo.
- Copy UI tiếng Anh 100%. Không hiển thị nguyên văn bình luận của follower.
- **Ba người đọc, hai ngôn ngữ** (Thy chốt 2026-10-29): mỗi khối viết cho cùng lúc (1) Thy, (2) người không chuyên
  — recruiter, người xem portfolio, thường không đọc tiếng Việt — và (3) người chuyên môn DS/MLE/tech lead.
  - Người chuyên môn: đủ lập luận kỹ thuật (phương pháp, n, effect size, CI, hiệu chỉnh, giới hạn) — ở câu chính
    hoặc "Method and limits", không cắt bớt để "dễ đọc".
  - Người không chuyên: câu trả lời bằng chữ thường trước; mọi thuật ngữ được định nghĩa (tại chỗ hoặc bảng thuật
    ngữ của trang, có link tới); không mã nội bộ trần (`topic_N`, `RQ-01`) khi chưa giải thích.
  - Song ngữ: chữ gốc tiếng Việt / Pháp (dòng đầu bài, bài đại diện, từ khoá, hover) không bao giờ đứng một mình —
    mỗi dòng / khối hiện chữ gốc kèm ngữ cảnh tiếng Anh ngay trên dòng đó (tối thiểu tên topic tiếng Anh, VD cột
    "Topic (English)"; tóm tắt / dịch tiếng Anh khi dữ liệu có) và ghi rõ "original language".
  - Trước khi báo "done": đọc trang 3 lượt, mỗi lượt đóng 1 vai; `@agent-copy-reviewer` kiểm mục "Luồng đọc song ngữ".
- **Trình bày như nhà nghiên cứu NLP** (luật chặt, Thy chốt 2026-10-29 sau khi bác bản /topics đầu):
  - Không in số/tham số trần: mỗi số đi kèm nó là gì, tính thế nào (công thức), vì sao quan trọng. Dòng mono
    toàn tham số (`model → UMAP (…) → HDBSCAN …`) chỉ được là lớp phụ, ngay dưới bản giải thích từng bước.
  - Trang phân tích có phần "cách tính" với công thức + nghĩa của từng ký hiệu (VD Topics: embedding/cosine,
    UMAP, HDBSCAN, c-TF-IDF, độ tương đồng với tâm, DBCV, ARI, Cliff's δ, Brunner-Munzel, Holm).
  - "Method and limits" **mở sẵn**; nút thu gọn trông rõ là nút (viền/nền + chevron, vùng chạm 44px), không như link.
  - Gạch đầu dòng dọc, câu ngắn, phân tầng (ý chính → chi tiết); không 2 khối chữ dày đặt cạnh nhau; đoạn văn
    > 3 câu → tách thành bullet (tiêu chí biên tập).
  - Nhãn phân loại (cột "result", trạng thái) có chú giải ngay cạnh bảng và khác nhau thấy được (màu/ký hiệu +
    chữ), người đọc phân biệt được không cần hover.
  - Bố cục: không khoảng trắng lớn vô cớ (khối câu trả lời trải đủ bề rộng card, hoặc cột phải có nội dung); thẳng
    lưới; chữ không sát mép card; không thanh cuộn lồng trong khối chỉ vì nội dung tràn vài px.
  - Cỡ chữ theo thang cố định của `design-system.md` §3; mỗi khác biệt cỡ chữ có mục đích (cấp tiêu đề), không tuỳ
    hứng từng khối.
  - Trước khi báo "done" hay commit UI: chạy `@agent-ux-reviewer` (ảnh chụp thật, nhiều khổ màn hình); lỗi mức
    "chặn" phải sửa.
- Header trang app (`<header>` dưới Nav) đặt nội dung trong cùng khung `mx-auto max-w-[1280px] px-6` với Nav và
  `<main>` — thiếu khung thì trên màn hình rộng tiêu đề dạt mép trái, lệch với phần thân.
- Next.js 16 có breaking changes so với kiến thức cũ — đọc `src/dashboard/AGENTS.md` và `node_modules/next/dist/docs/`, hoặc MCP `context7`.
- Xong việc UI: `npm run lint` + `npm run typecheck` + `npm run build` + `uv run python -m scripts.consistency.check --commit` sạch (sổ luật bắt chữ cấm mà lint/pytest không bắt), và xem thật trước khi báo "done" (trình duyệt, hoặc `npm run screenshots` rồi mở ảnh).
