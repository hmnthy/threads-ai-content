# ADR-0031: Ba trang app theo một khuôn khối, một tên "content units", số toàn kênh cho cả 3 tỉ lệ

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-31
- **Người quyết**: Thy (chọn qua câu hỏi 2026-10-31 trong lúc làm PR 2a của sổ luật UI: đầu trang căn giữa dùng chung,
  làm hết trong 1 PR, một tên "content units", tên topic tiếng Anh cạnh mỗi content unit, câu hỏi Overview, câu trả
  lời Analytics có số mô tả + mở rộng API, eyebrow theo lớp của landing, ngữ cảnh tiếng Anh đứng trước, thứ tự khối
  Overview); cách làm do Claude đề xuất

## Bối cảnh

- Sau PR sổ luật (ADR-0029, ADR-0030), máy đo `ux-shots.mjs` của 3 trang app về 0, nhưng `@agent-ux-reviewer` còn 15
  lỗi chặn chấm bằng mắt, gần hết có từ trước:
  - Overview và Analytics không theo khuôn khối của Topics (câu hỏi → câu trả lời → bằng chứng → "Method and limits"):
    không câu trả lời, không công thức của 3 tỉ lệ, tiêu đề giả;
  - 3 kiểu nút bật/tắt, 2 kiểu số KPI (dải KPI của Overview lặp số của dải hero);
  - chữ gốc tiếng Việt trong danh sách bài không có ngữ cảnh tiếng Anh (B2);
  - cùng một đối tượng mang 3 tên: "content units" (Topics), "posts" / "root posts" (Analytics, Overview).
- `@agent-copy-reviewer` thêm: câu trả lời khối Analytics chỉ nói phạm vi, không trả lời câu hỏi; định nghĩa
  engagement trên thẻ chỉ số sai ("share of views that led to any reaction" — một người xem có thể phản ứng nhiều lần).
- API `/analytics/overview` chỉ trả phân phối toàn kênh của engagement rate (`src/main.py:274#engagement`), nên tab share rate và
  conversation rate không so được top với kênh.

## Quyết định

1. **Một khuôn khối cho 3 trang app**: đầu trang dùng chung `PageHeader` (`src/dashboard/src/components/AppBlock.tsx:72#PageHeader`
   — eyebrow → h1 → câu hỏi → định nghĩa đơn vị đếm → chip mốc dữ liệu → mục lục khối); mỗi khối là `Section` + câu
   trả lời (+ Key numbers) + bằng chứng + "Method and limits" mở sẵn; một kiểu nút bật/tắt `ToggleGroup` (`:146#ToggleGroup`).
   Overview: 01 cửa sổ thời gian → 02 nhiều views nhất → 03 các chỉ số; dải KPI bỏ. Analytics: 01 xếp hạng theo tỉ lệ
   → 02 giờ và ngày đăng.
2. **Một tên "content units"** trên mọi trang; Overview và Analytics định nghĩa nó ngay dưới câu hỏi đầu trang (cùng câu
   với khối 01 của Topics, `src/dashboard/src/lib/appSections.ts:17#CONTENT_UNIT`).
3. **Chữ gốc không đứng một mình**: mỗi content unit trong danh sách / bảng có dòng ngữ cảnh tiếng Anh nằm trên chữ
   gốc (`UnitText`, `AppBlock.tsx:201#UnitText` — "Topic: X · original language" / "Unclustered: fits none of the N topics" /
   "Published after the latest topic run"; "Unclustered" cùng tên với trang Topics). Tên topic ghép phía server từ `/content-units` + `/topics`
   (`src/dashboard/src/lib/load.ts:46#loadAppContext`), không đổi API. Bảng dùng chữ 13px, danh sách 15px.
4. **Câu trả lời nêu số mô tả, kèm "chưa kiểm định"**: Analytics 01 nêu khoảng của top N theo tỉ lệ đang chọn và
   median toàn kênh của đúng tỉ lệ đó; Analytics 02 nêu khoảng median của các ô đọc được, không nêu tên ô cao nhất;
   Overview 01 nêu median engagement rate của cửa sổ kèm median của mọi content unit đã thu, ghi "(not tested)".
   `/analytics/overview` thêm `share_rate` và `conversation` (median + IQR + n toàn kênh, cùng tập bài đo được như
   `engagement`, `src/main.py:277-278#share_rate`, `:795-796#share_rate`).
5. **Eyebrow nối với lớp của landing**: "MEASURE · ONE TIME WINDOW", "MEASURE · RANKINGS AND POSTING TIME",
   "GROUP · TOPICS FROM TEXT".

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Sửa nhanh ở PR 2a, viết lại cấu trúc ở PR 2c | PR nhỏ hơn | Gate mắt vẫn FAIL tới PR 2c | Thy chọn làm hết trong 1 PR |
| "posts" ở Overview/Analytics, "content units" ở Topics | Dễ hiểu với người mới | 2 tên cho 1 đối tượng | Thy chọn một tên + định nghĩa trên mỗi trang |
| Tạm ghi "Original language", tên topic để PR sau | Ít việc | B2 còn thủng | Thy chọn làm đủ ngay (ghép phía server) |
| Câu trả lời Analytics chỉ nêu khoảng top N, không đổi API | Không đổi backend | 2/3 tab không so được với kênh | Thy chọn mở rộng API |
| Giữ eyebrow "CHANNEL OVERVIEW" / "TOPIC ANALYSIS" | Không đổi | Lặp tiêu đề | Thy chọn nối với lớp landing |
| Giữ khối "Measures" ở giữa Overview | Đúng thứ tự tầng A cũ | Chen giữa 2 khối cùng trả lời câu hỏi đầu trang | Thy chọn chuyển xuống cuối |

## Hệ quả

- Code: `src/main.py` (`AnalyticsOverviewOut.share_rate`, `.conversation`) + test
  `tests/test_main.py::test_analytics_overview_ranks_top_posts_per_metric_and_breaks_down_by_timezone`; dashboard:
  `AppBlock.tsx` (`PageHeader`, `ToggleGroup`, `UnitText`, `LoadError`), `lib/load.ts` (`loadAppContext`),
  `lib/appSections.ts`, 3 trang trong `app/(app)/`, `OverviewDashboard`, `TopContentList`, `MetricArchitectureGrid`,
  `TimelineBrush`, `AnalyticsBreakdown`, `PostingTimeHeatmap`; `KpiStrip.tsx` bỏ.
- Docs: `docs/claude/design-system.md` §6, §7, §13; `docs/design/ui-contract.md`.
- Luật: `ADR0031-old-app-copy` cấm câu cũ trên trang app ("Root posts analyzed", "root posts in window", định nghĩa
  engagement sai, phụ đề "stand out on each index"); quét cả mockup (cảnh báo).
- Nợ chấp nhận: landing (PR 2b) chưa theo khuôn này; dòng ngữ cảnh của content unit không thuộc topic nào vẫn không có
  tóm tắt tiếng Anh — cần tóm tắt tiếng Anh từng bài (đề xuất "tóm tắt tiếng Anh từng bài", chưa có ADR).
- Xem lại khi: có tóm tắt tiếng Anh từng content unit (thay dòng "Unclustered: …" / "Topic: …"); thêm trang app mới (dùng `PageHeader` +
  `Section`); hoặc API đổi tập bài đo được.

### Hệ quả UI

- Thêm: `UI-0031-page-shape` (đầu trang + khuôn khối chung), `UI-0031-content-unit-term` (một tên + định nghĩa),
  `UI-0031-unit-context` (ngữ cảnh tiếng Anh trước chữ gốc, tên topic ghép phía server),
  `UI-0031-channel-rates` (`share_rate` + `conversation` toàn kênh, câu trả lời Analytics có số mô tả).
- Nâng mốc "Cập nhật tới: ADR-0031" của `docs/design/ui-contract.md`.
