# ADR-0035: Analytics có khối "một content unit so với kênh" trên cả 3 tỉ lệ, dùng chung với panel hero của landing

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-02
- **Người quyết**: Thy — duyệt gói 1–3 + sửa bìa của `/promise-audit` 2026-11-02, rồi chọn qua câu hỏi 2026-11-02: khối
  mới 02 ở `/analytics`; chọn bài bằng ô tìm kiếm + nút trên từng dòng bảng top; cả 3 tỉ lệ; hộp Key numbers chỉ ở
  `/analytics`; link từ panel hero landing; cột trùng giá trị gộp + nhãn đếm; duyệt toàn bộ chữ. Cách làm do Claude đề xuất.

## Bối cảnh

- `/promise-audit` 2026-11-02 (commit 0606efb; báo cáo riêng tư `data/audits/promise-gap/`): mức 4 "bìa hứa sai", độ
  phủ 30/37, còn 3 lời hứa S1:
  - câu hero "Unthreaded shows how each content unit on a Threads channel did compared with the rest of that channel":
    không trang app nào đặt được một bài bất kỳ vào phân phối của kênh — `/analytics` chỉ có top N trên sàn views P25;
  - câu hero "Every figure says how many content units it rests on": 2 số ARI của khối độ bền (dùng chung `/topics` và
    landing) không ghi n, API cũng không trả;
  - câu sơ đồ landing "Charts are hand-built SVG" sai kỹ thuật: chỉ timeline views theo ngày và chính sơ đồ là SVG, mọi
    biểu đồ còn lại là `div` HTML/CSS, bản đồ topic là Plotly `scatter3d` (WebGL).
- Phép xếp hạng một bài đã có và Thy đã duyệt (panel hero landing, ADR-0032; `rankAmongOthers`,
  `src/dashboard/src/lib/landing.ts:389#rankAmongOthers`): đếm bài có tỉ lệ thấp hơn hẳn, chia cho số bài còn lại, làm
  tròn xuống; "Yes" = trên median. Chỉ bài mẫu cố định dùng được nó.
- n của ARI đã lưu sẵn: mỗi lần gom cụm ghi bảng chuyển `transitions_json` (`src/pipeline/clustering_import.py:169#compare_with_previous`
  — 4 ô cụm/nhiễu → cụm/nhiễu = tập ARI tính cả unclustered; ô cụm → cụm = tập ARI chỉ topic). Dữ liệu thật 2026-11-02:
  163 content units có mặt ở cả 2 lần chạy và 110 có topic cả 2 lần; 29/29 lần chạy có bảng này.
- Share rate và conversation rate có nhiều bài trùng 0%: 37/163 bài không có repost/quote, 10/163 bài không có reply
  (dữ liệu 2026-11-02). Với khoảng cách chấm 9px, cột 37 chấm cao ~340px, tràn khung biểu đồ 250px.
- `/topics` chỉ trả median/IQR engagement theo topic; so "cùng topic" trên share / conversation rate cần backend tính
  (luật dashboard: median/IQR không tính lại ở trình duyệt).

## Quyết định

1. `/analytics` thêm **khối 02 "One content unit"** (giờ đăng thành 03): người đọc chọn một content unit có views (ô
   tìm kiếm combobox, hoặc nút "Compare ↓" trên mỗi dòng bảng top — mang theo tỉ lệ của tab đang xem) và một trong **3
   tỉ lệ**, so với cả kênh hoặc với topic của nó. Phần thân là **một component dùng chung với panel hero của landing**
   (`src/dashboard/src/components/UnitVsChannel.tsx:50#UnitVsChannel`): cùng phép xếp hạng, câu trả lời, Method. Hộp
   Key numbers + "What to know" chỉ ở `/analytics`; landing giữ panel hero như ADR-0032 và thêm link tới `/analytics#unit`.
   Cột chấm trùng giá trị cao hơn khung được vẽ gọn kèm nhãn đếm đúng số bài (chiều cao biểu đồ giữ nguyên giữa 3 tỉ lệ).
2. API: `/topics` trả thêm `share_rate` + `conversation` theo topic, cùng tập bài đo được và cùng công thức với
   `/analytics/overview` (`src/main.py:254-255#share_rate`); `/pipeline/summary` trả n của 2 ARI (`ari_n_common`,
   `ari_n_clustered_both`) đọc từ `transitions_json` (`src/main.py:1048#_ari_counts`) — không đổi schema. Khối độ bền
   ghi n cạnh mỗi ARI (chỉ khi có ARI), cách DBCV tính trọng số (n gồm cả unclustered, kéo điểm về 0) và giờ gom cụm.
3. Thay một phần ADR-0031 cho trang Analytics: thứ tự khối 01 xếp hạng → 02 một content unit → 03 giờ và ngày đăng
   (`src/dashboard/src/lib/appSections.ts:10#ANALYTICS_SECTIONS`; mục 1 và câu "Analytics 02" ở mục 4 của ADR-0031),
   eyebrow "MEASURE · RANKINGS, ONE CONTENT UNIT, POSTING TIME" (mục 5). Phần còn lại của ADR-0031 giữ nguyên.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Cột thứ hạng trong bảng mọi content unit của `/topics` | Ít việc | Không beeswarm, không so cùng topic; chỉ khép một phần lời hứa | Thy chọn khối mới ở `/analytics` (ADR-0023 1a: Analytics trả lời "bài nào hiệu quả?") |
| Làm cả khối mới lẫn cột ở `/topics` | Hai lối vào | Nhiều việc nhất | Thy chọn khối mới |
| Chỉ ô tìm kiếm (không nút trên bảng top) | Ít việc | Không nối khối 01 với 02 | Thy chọn ô tìm kiếm + nút trên dòng |
| Bấm chấm trên beeswarm để chọn | Trực quan | Chấm 6–9px dưới vùng chạm 44px (C4), khó dùng bằng bàn phím | Không đạt sổ luật |
| Chỉ engagement rate | Đúng lời hứa của landing, không đổi backend | Nút "Compare" ở tab share / conversation đổi thước đo mà không báo | Thy chọn mở rộng cho 3 tỉ lệ (sau khi reviewer nêu lỗi đổi thước đo) |
| Ẩn nút "Compare" ở tab share / conversation | Gọn | Mất lối vào cho 2 tỉ lệ | Thy chọn mở rộng khối |
| Không hộp Key numbers (giống panel hero) | Một hình khối với landing | Median, IQR, n rải ở 3 chỗ trên biểu đồ (K5) | Thy chọn thêm, chỉ ở `/analytics` |
| Khung biểu đồ cao theo dữ liệu (thấy đủ từng chấm) | Không cắt chấm nào | Chiều cao khối nhảy khi đổi tỉ lệ | Thy chọn gộp cột + nhãn đếm |
| Thêm cột vào `cluster_runs` cho n của ARI | Trường riêng, rõ nghĩa | Đổi schema, cron chạy code thư mục chính | `transitions_json` đã có đúng số đếm |

## Hệ quả

- Code:
  - API `src/main.py` (`TopicOut.share_rate` / `.conversation`, `ClusterRunOut.ari_n_common` /
    `.ari_n_clustered_both`, `_ari_counts`) + test `tests/test_main_pipeline.py`
    (`test_topics_report_share_and_conversation_rate_of_the_same_measurable_members`,
    `test_pipeline_summary_ari_n_matches_the_units_the_ari_was_computed_on`,
    `test_pipeline_summary_first_run_has_zero_ari_n_and_no_ari`).
  - Dashboard: `UnitVsChannel.tsx`, `UnitPicker.tsx` (mới); `LandingHero.tsx` dùng component chung;
    `AnalyticsBreakdown.tsx` (khối 02, nút "Compare ↓", khối 02 hiện từ HTML server — không chờ dữ liệu khối 01);
    `lib/landing.ts` (`RATE_INFO` — một nguồn tên + công thức 3 tỉ lệ, `byRate`, `rateAxis`); `lib/load.ts`
    (`withComparison`); `AppBlock.tsx` (`ActionButton` — một kiểu nút hành động); `lib/typeScale.ts` (`TYPE.control`);
    `TopicsView.tsx` (`StabilityPanel`).
  - Sửa 2 câu bìa (promise-audit 2b): node "Dashboard · Landing" của `LandingTechStack.tsx`, Limits "re-read every 4
    hours while the collecting laptop is awake"; dòng Dashboard của 3 README.
- Docs: `docs/design/ui-contract.md` (dòng mới + sửa `UI-0031-page-shape`, `UI-0031-channel-rates`),
  `docs/design/ui-contract-audit.md` (chữ Thy duyệt 2026-11-02).
- Luật: `ADR0035-old-chart-tech` (câu "hand-built SVG" ở landing + README 3 thứ tiếng), `ADR0035-old-analytics-shape`
  (eyebrow "Rankings and posting time", thứ tự "01 xếp hạng → 02 giờ đăng" trong hợp đồng), `ADR0035-old-refresh-limit`
  (Limits cũ "latest counts (re-read every 4 hours)" — thiếu điều kiện laptop thức). Cả 3 quét mockup (cảnh báo).
- Nợ chấp nhận:
  - bài unclustered vẫn chỉ có nhãn "Unclustered: …", chưa có tóm tắt tiếng Anh (đề xuất "tóm tắt tiếng Anh từng bài",
    chưa có ADR); bài mẫu của landing có nghĩa tiếng Anh viết tay (`HERO_ENGLISH`);
  - máy đo `ux-shots.mjs` chỉ chụp trạng thái mặc định — trạng thái share / conversation rate, combobox mở, bài ở 2 đầu
    phân phối chỉ được reviewer chụp tay;
  - thứ hạng là mô tả, không kiểm định (ghi ở Method + "What to know").
- Xem lại khi: có tóm tắt tiếng Anh từng content unit; có luật bền theo seed (RQ-01) — khi đó thứ hạng trong topic có
  thể cần ghi chú độ bền của topic; hoặc API thêm tỉ lệ thứ tư.

### Hệ quả UI

- Thêm: `UI-0035-unit-vs-channel` (khối 02 `/analytics` + panel hero dùng chung `UnitVsChannel`, 3 tỉ lệ, tập so, cột
  gộp + nhãn đếm, Key numbers chỉ ở `/analytics`, link landing), `UI-0035-ari-n` (n cạnh mỗi ARI, giờ gom cụm, trọng số
  DBCV trong khối độ bền).
- Sửa: `UI-0031-page-shape` (3 khối Analytics, eyebrow mới), `UI-0031-channel-rates` (giờ đăng là Analytics 03; `/topics`
  có `share_rate` + `conversation`), `UI-0004-ari-two-ways` (`transitions_json` nay lên API qua n).
- Nâng mốc "Cập nhật tới: ADR-0035" của `docs/design/ui-contract.md`.
