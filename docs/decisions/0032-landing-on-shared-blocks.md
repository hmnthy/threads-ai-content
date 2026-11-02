# ADR-0032: Landing dùng lại khối của trang app, một tên "content units", 3 điều chỉnh sổ luật

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-01
- **Người quyết**: Thy (chọn qua câu hỏi 2026-11-01 trong lúc làm PR 2b của sổ luật UI: ngoại lệ T5 cho panel hero,
  câu hỏi làm tiêu đề panel hero, hero không hộp Key numbers, panel Proof dùng lại bản /topics + câu hỏi "differ", bản
  đồ 3D nhiều màu, Problem 3 cột, sơ đồ 960px + danh sách dọc, vai nút CTA 15px, một tên "content units" trên landing;
  sau lượt review: ngoại lệ X8 cho chữ căn giữa, mục lục dưới đầu Proof, nút CTA thứ hai sang /topics);
  cách làm do Claude đề xuất

## Bối cảnh

- Sau ADR-0029/0030/0031, máy đo `ux-shots.mjs` của 3 trang app về 0 nhưng landing còn 27 vi phạm + 1 vi phạm giữa các
  trang (display-2 có 4 kiểu: 46 / 46 trên dải tối / 38 / 52px). `@agent-ux-reviewer` (lượt "trước khi sửa", ảnh
  `data/ux-shots/2026-11-01-13-13`) thêm 11 lỗi chặn bằng mắt:
  - mọi panel có "tiêu đề giả": câu hỏi 13px màu cam đứng trên câu trả lời 24px (T4–T6);
  - landing không dùng component nào của `AppBlock.tsx` (C2): nút "Method and limits" trông như link (C3), phần Method
    mở ra là 2 khối chữ dày cạnh nhau, công thức thiếu nghĩa ký hiệu (N2), số trần (DBCV, ARI, similarity — N1), nhãn
    kết quả chỉ khác nhau bằng màu (N3), topic đang chọn thiếu IQR và hiện mã `topic_N` (N4, B3);
  - chữ tiếng Việt không có ngữ cảnh tiếng Anh (B2); section Problem để trống ~360px (L5); sơ đồ "How it works" rộng cố
    định 1136px nên cuộn ngang cả ở màn 1024px.
- Panel "topic so với kênh" có 2 bản viết riêng: bản landing và bản /topics (bản /topics đã đạt sổ luật, ADR-0029/0031).
- Landing gọi đơn vị đếm là "posts", 3 trang app gọi là "content units" (ADR-0031).

## Quyết định

1. **Landing dùng lại chính các khối của trang app** (C2): ngữ cảnh `LandingBlocks`
   (`src/dashboard/src/components/AppBlock.tsx:25#LandingBlocks`) đổi hình khối theo tầng B — tiêu đề lùi 1 cấp (X1, component tiêu
   đề `H`, `:43#H`), panel bo 20px (X3), "Method and limits" thu gọn sẵn (X5), link thuật ngữ trỏ sang bảng thuật ngữ của
   /topics (`TermMore`, `:517#TermMore`), số + tên ngắn của khối theo id. Section Proof (`LandingProofSection.tsx:23#LandingProof`) = 3 khối
   của /topics: chủ đề + bản đồ 3D nhiều màu (`TopicProfilePanel`, bỏ bảng mọi content unit, `TopicsView.tsx:151#TopicProfilePanel`),
   topic so với kênh (`TopicEngagementPanel`, `LandingProof.tsx:39#TopicEngagementPanel` — câu hỏi "differ" như /topics), độ bền
   (`StabilityPanel`, `TopicsView.tsx:627#StabilityPanel`). Bản landing riêng của panel engagement và panel cấu trúc bỏ.
2. **Panel hero theo khuôn khối chung**: tiêu đề = chính câu hỏi (h3 26px), câu trả lời trong khung ANSWER trải hết bề
   rộng, không hộp Key numbers (dải 4 số phía trên đã đủ), nút chọn tập so sánh là `ToggleGroup` "Compare with", Method
   có từng bước + công thức (`LandingHero.tsx:127#example`; từ 2026-11-02 thân panel là component chung
   `src/dashboard/src/components/UnitVsChannel.tsx:383#MethodSection`, dùng cả ở khối 02 của /analytics).
3. **Sổ luật thêm 3 điểm**:
   - ngoại lệ T5 duy nhất (§3b X7): tiêu đề khối của panel hero landing (`[data-ux="hero-panel"]`) được nằm ngay dưới
     display-1 — máy đo chỉ cho chính tiêu đề đầu tiên của panel đó (`scripts/ux-shots.mjs:188#heroTitle`, 3 trang mẫu trong
     `ux-shots-fixtures.mjs`);
   - ngoại lệ **X8**: chữ căn giữa của hero và khối CTA cuối giới hạn ~640–720px vì độ dài dòng (ngoại lệ của L5); chữ
     căn trái của các section trải hết bề rộng;
   - vai **CTA 15px w600** (`TYPE.cta`, `src/dashboard/src/lib/typeScale.ts:35#cta`) cho nút chính của trang giới thiệu
     (hero + CTA cuối); mọi nút / tab / pill khác vẫn là control 13px.
4. **Bố cục landing**: Problem — đầu section trải ngang, Q1–Q3 thành 3 cột từ 1024px, cùng lưới với 3 tầng Measure /
   Group / Search của Approach (`LAYER_GRID`, `LandingParts.tsx:55#LAYER_GRID`), mỗi câu hỏi là h3 26px; Approach xếp dọc dưới
   1024px; sơ đồ "How it works" vẽ ở 960px, dưới 1024px là danh sách các bước xếp dọc. Mọi đầu section (kể cả About,
   CTA) dùng một display-2. Proof có dải mục lục 3 khối ngay dưới đầu section (`SectionIndex`, cùng kiểu mục lục đầu
   trang app). Nút thứ hai của khối CTA là "Explore all topics" → /topics (không đưa ngược lên sơ đồ).
5. **Một tên "content units" trên cả landing**, định nghĩa một lần dưới dải số đầu trang (cùng câu với các trang app,
   `src/dashboard/src/lib/appSections.ts:18#CONTENT_UNIT`). "post" chỉ còn khi nói về đối tượng của chính Threads.
5b. **Khối CTA cuối không còn logo** (Thy 2026-11-01: viền trắng của logo lộ trên dải tối; `UI-0021-logo-placement` sửa
   theo).
6. **Overview (đi kèm, Thy 2026-11-01 khi duyệt PR 2b)**: biểu đồ views theo ngày + thanh kéo nằm ngay dưới đầu khối 01
   (`src/dashboard/src/components/OverviewDashboard.tsx:113#TimelineBrush`), dải hero + câu trả lời ở dưới — kéo tới đâu số đổi ngay
   bên dưới; chuỗi bắt đầu từ ngày có content unit đầu tiên (`firstPostDate`, `src/dashboard/src/lib/load.ts:85#firstPostDate`), đoạn
   trước đó không hiện (thiếu ngày đầu hoặc còn < 2 điểm thì giữ cả chuỗi). Tạm cắt từ ngày đầu − 1 ngày: code-reviewer
   phát hiện (đã kiểm lại trên data thật) backend gắn nhãn chuỗi views sớm 1 ngày — 8/10 bài đăng riêng lẻ có đỉnh views
   ở ngày trước khi đăng; Thy chọn sửa tận gốc ở PR riêng có ADR (sửa `src/api/endpoints.py`, dời nhãn dữ liệu đã lưu,
   test "đỉnh views trùng ngày đăng"), rồi gỡ phần bù.
7. Hằng `TYPE` chuyển sang `src/dashboard/src/lib/typeScale.ts` (file thường): server component đọc hằng xuất từ module
   "use client" chỉ nhận được tham chiếu, ra `undefined` (mọi chữ landing rơi về 16px ở lần chạy đầu).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Bọc panel hero trong section "00 · Example" có display-2 | Đúng T5 không cần ngoại lệ | Trang dài thêm ~200px | Thy chọn ngoại lệ |
| Tiêu đề hero ngắn, câu hỏi xuống dòng mục đích | Tiêu đề 1 dòng | Khác /topics (tiêu đề là câu hỏi) | Thy chọn câu hỏi làm tiêu đề |
| Hero có hộp Key numbers | Đủ khuôn khối | Lặp median của dải số | Thy chọn không |
| Giữ 2 bản panel, chỉ sửa cỡ chữ bản landing | Panel landing ngắn | Trái C2, 2 bản lệch nhau | Thy chọn dùng lại bản /topics |
| Bản đồ 2D nhẹ trên landing | Không cần WebGL | Khác màu bản đồ app (cần ngoại lệ X) | Thy chọn 3D như /topics |
| Problem giữ 2 cột, cột trái dính | Ít đổi | Vẫn 2 khối chữ cạnh nhau | Thy chọn 3 cột |
| Sơ đồ giữ cuộn ngang, chỉ thêm focus bàn phím | Ít việc | Màn laptop vẫn phải cuộn | Thy chọn vẽ lại 960px |
| Ép nút CTA về 13px | Không sửa sổ luật | Nút chính yếu trên landing | Thy chọn vai CTA 15px |
| Giữ "posts" trên landing | Thân thiện người mới | 2 tên cho 1 thứ giữa landing và dashboard | Thy chọn "content units" |

## Hệ quả

- Code: `AppBlock.tsx` (`LandingBlocks`, `H`, `TermMore`, `Section` nhận `ux`), `lib/typeScale.ts`, `LandingHero`,
  `LandingProblem`, `LandingSolution`, `LandingTechStack`, `LandingAuthor`, `LandingCta`, `LandingNav`, `LandingParts`
  (bỏ `MethodButton`, `MethodBlock`, `PANEL`, `APP_CARD`), `LandingProofSection.tsx` (mới), `LandingProof.tsx` (chỉ còn
  panel dùng chung), `TopicsView.tsx` (xuất 2 panel), `app/page.tsx`; máy đo `scripts/ux-shots.mjs` + trang mẫu.
- Docs: `docs/claude/design-system.md` §3 (vai CTA, nơi đặt `TYPE`), §3b T5 + X7 + X8, §7 (tầng B), §13;
  `docs/design/ui-contract.md`; `docs/design/landing-handoff.md` (banner: bố cục cũ là lịch sử); mục ADR-0032 của
  `docs/design/ui-contract-audit.md`. Harness riêng (`.claude/rules/dashboard.md`, `.claude/agents/ux-reviewer.md`)
  còn ghi "X1–X6" — sửa trong kho harness (ADR-0027), không trong repo này.
- Luật: `ADR0032-old-landing-copy` cấm câu cũ của landing ("Which topics get a higher engagement rate than the rest of
  the channel?", "the channel's usual post", "Same topic · none"); quét cả mockup (cảnh báo). `ADR0032-single-accent-id`
  cấm id hợp đồng bản đồ 2D đã bỏ; `ADR0032-whitelist-x1-x6` cấm "X1–X6" (danh sách trắng nay là X1–X8); `ADR0032-cta-no-logo` cấm câu "khối CTA
  mark 52px" (mục 5b). Tên "posts" không cấm bằng
  regex được (Threads vẫn gọi đối tượng của nó là post) — copy-reviewer kiểm.
- Kết quả đo: UX gate (máy) PASS trên cả 4 trang lần đầu từ khi có sổ luật.
- Xem lại khi: thêm panel hero thứ hai hoặc trang giới thiệu khác (ngoại lệ X7 chỉ cho 1 panel); landing cần tải nhẹ
  hơn (bản đồ 3D); có tóm tắt tiếng Anh từng content unit.

### Hệ quả UI

- Thêm: `UI-0032-overview-brush-first` (thanh kéo đầu khối 01 Overview, chuỗi từ bài đầu tiên),
  `UI-0032-landing-shared-blocks` (landing dùng lại khối app qua `LandingBlocks`), `UI-0032-hero-panel`
  (khuôn panel hero + ngoại lệ T5), `UI-0032-landing-term` (một tên "content units" trên landing),
  `UI-0032-landing-layout` (Problem 3 cột, sơ đồ 960px, mục lục Proof, vai `cta`, nút 2 CTA, X8).
- Sửa: `UI-L20261029-topic-categorical` áp cả landing (bản đồ 3D nhiều màu); `UI-0029-landing-whitelist` (X1–X8);
  `UI-L20260903-landing-vs-app-routes` (nút 2 CTA → /topics); `UI-L20260829-mobile` (landing xếp dọc dưới 1024px);
  `UI-0024-partition-history` (ref của panel dùng chung); `UI-0021-logo-placement` (khối CTA không logo); `UI-0011-two-exclusions` trỏ sang panel
  dùng chung; `UI-0024-exploratory-comparisons`, `UI-L20260903-small-n-flag` trỏ sang câu của panel dùng chung.
- Bỏ: `UI-L20260930-topic-single-accent` (bản đồ 2D một màu nhấn của landing không còn).
- Nâng mốc "Cập nhật tới: ADR-0032" của `docs/design/ui-contract.md`.
