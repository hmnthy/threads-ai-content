# Audit mockup theo hợp đồng UI

> Kiểm 2026-10-07 (vòng 3) trên gói Claude Design 2026-10-07, theo `docs/design/ui-contract.md` (Cập nhật tới: ADR-0020;
> gồm luật ADR-0012).
> **Người đọc:** Claude Design (sửa mockup ở vòng kế tiếp) và Claude Code (khi port). Claude Code **không sửa mockup**
> (ADR-0020). Số liệu cũ trong mockup (số bài, %, median…) không nằm trong audit này — xử lý riêng khi có file xuất
> (brief Việc 4).
> **Mức:** `cấu trúc` = phải đổi component / trạng thái / dạng dữ liệu / luồng; `chữ` = chỉ đổi câu chữ.

## 1. Cảnh báo tự động của sổ luật

Nguồn: `uv run python -m scripts.consistency.check --all` — mục "Cảnh báo mockup" (không chặn commit). Hook đầu phiên
in số cảnh báo; khi về 0, hàng này xoá. Hiện (2026-10-09, Việc 3): **9** (1 báo nhầm + 2 theo ADR-0021 + 6 theo
ADR-0023). 8 cảnh báo ADR-0012 của vòng 2 đã hết.

| File mockup | Dòng | Luật | Khớp | Xử lý |
|---|---|---|---|---|
| `src/dashboard/mockups/landing.dc.html` | 533 | `ADR0001-coming-soon` | "sắp có" | **Báo nhầm**: nội dung bài gốc tiếng Việt dùng làm dữ liệu mẫu, không phải nhãn trạng thái. Hết khi mockup lấy dữ liệu từ file xuất <!-- consistency: allow ADR0001-coming-soon --> |
| `src/dashboard/mockups/landing.dc.html` | 258, 558 | `ADR0023-old-test-engine` | tên kiểm định cũ | Theo câu Method mới ở mục "Việc 3" bên dưới |
| `src/dashboard/mockups/landing.dc.html` | 557 | `ADR0023-topic-tests-next` | node API "Per-topic comparisons are next." | Theo câu node API ở mục "Việc 3" bên dưới <!-- consistency: allow ADR0023-topic-tests-next — trích nguyên văn mockup để Claude Design sửa --> |
| `src/dashboard/mockups/landing.dc.html` | 150 | `ADR0023-topic-tests-next` | lớp 01 Measure "Comparing groups with an effect size is next." | Theo câu Approach lớp 1 ở mục "Việc 3" |
| `src/dashboard/mockups/landing.dc.html` | 210 | `ADR0023-more-engagement-question` | câu hỏi panel 1 "…more engagement than the channel?" | "Which topics get a higher engagement rate than the rest of the channel?" |
| `docs/design/layout-tiers.dc.html` | 172 | `ADR0023-more-engagement-question` | như trên (minh hoạ khối tầng A) | như trên |
| `src/dashboard/mockups/overview-amber.dc.html` | 30 | `ADR0021-placeholder-logo` | logo giữ chỗ bằng icon "at" trong vòng tròn amber | Logo `../public/brand/unthreaded-lockup.svg` cao 36px, tagline chữ HTML 15px cạnh logo ngăn bằng vạch dọc (`UI-0021-logo-placement`, `UI-0026-logo-replay`; trên web logo phát lại hoạt cảnh mỗi 15 giây) |
| `src/dashboard/mockups/overview-cyan.dc.html` | 30 | `ADR0021-placeholder-logo` | như trên | như trên (hoặc bỏ file — hướng không chọn) |

## 2. Landing so với hợp đồng

`src/dashboard/mockups/landing.dc.html` bản 2026-10-07. 3 điểm của vòng 2 đã sửa — Claude Code kiểm lại bằng tìm chuỗi:
không còn `lowN`, "under 10"; có "Paris time" (mốc đọc `RUN_AT_UTC`, đổi sang `Europe/Paris`), cờ `insufficient_data`
(n < 5), "not computed (fewer than 2 posts to compare)" cho ARI và "not computed (fewer than 2 clusters)" cho DBCV (xem
bằng tweak `ariNull`, `dbcvNull`). Không còn nhãn cũ của ADR-0012 ở mockup nào (hai luật `ADR0012-old-label-wording`, `ADR0012-raw-views-as-reach` hết cảnh báo). Còn lại:

| ui-contract id | Vị trí trong landing (dòng) | Hiện tại | Phải là | Mức |
|---|---|---|---|---|
| UI-0017-run-time | 500 (`RUN_AT_UTC`) | Giờ giữ chỗ `2026-10-01T12:30:00Z` (hiện 14:30 Paris time) | `run_at` thật của lần gom cụm cho số liệu mockup: `2026-10-01T11:35:06Z` → "2026-10-01 13:35 Paris time" (`cluster_runs.id = 3`, ghi ở handoff §0.5) | chữ |
| UI-L20260903-landing-vs-app-routes | 46, 473, 474 | "Read the methodology", "View the repo" trỏ `#` | URL thật khi deploy (handoff §3.7) — chưa phải lỗi | — |

### Port landing (PR 10, 2026-10-07) — chỗ code khác mockup

Code là bản port của mockup này; các chỗ dưới đây code **cố ý** khác, mockup nên theo ở vòng kế tiếp. Mọi số trên
landing giờ đọc từ API (`/content-units`, `/topics`, `/analytics/overview`, `/pipeline/summary`), không chép từ mockup.

| ui-contract id | Mockup | Code | Mức |
|---|---|---|---|
| UI-L20260829-mobile | Pill navbar `flex-wrap`: ở ~1360px nút "View live dashboard" rơi xuống hàng 2, khung sticky trong suốt che và chặn bấm nội dung | Pill luôn 1 hàng; dưới 1024px chỉ còn logo + nút; khung sticky không nhận chuột (`LandingNav.tsx`) | cấu trúc |
| UI-L20260903-stack-real-status | Panel 1 điền δ, p Holm, câu "None clearly…" và "computed offline from the 2026-10-01 snapshot" | Median/IQR/n theo topic là số thật (`TopicOut.engagement`); cột δ và p Holm hiện "—" kèm pill `next`; câu trả lời "<topic> has the highest median engagement rate among topics with enough posts to compare: X, against Y for the channel. The gap is not tested yet." (vế "among…" chỉ khi có topic mang cờ `insufficient_data`); cột "δ · next", "p, Holm · next"; dòng Preview: "medians and spread are live, Cliff's δ and Holm-corrected p-values are next" — từ Việc 3 (2026-10-09) chỉ còn là nhánh dự phòng khi API chưa có kết quả; chữ hiện hành ở mục "Việc 3" bên dưới | chữ |
| UI-0011-excluded | Panel 1 luôn ghi "6 excluded: no views recorded" | Chỉ hiện khi N > 0, N = số bài views = 0 trong các hàng của bảng (hiện 0 → ẩn) | chữ |
| UI-0004-ari-two-ways | Câu trả lời ARI viết cứng "Mostly, on posts that cluster at all…" | Sinh từ 2 số: cả hai = 1 → "This run matches the previous one exactly (ARI 1.00 on both measures). With the seed fixed, that shows it is reproducible, not that it is stable; stability across seeds is still research (RQ-01)."; khác → "Agreement a on posts clustered in both runs, b with noise counted."; cả hai null → "Not computed for this run." | chữ |
| UI-0004-representatives | "nearest post to the centre, similarity 0.888" luôn hiện ở thẻ Group | Chỉ ghi "nearest post to the centre" khi bài hero đứng đầu danh sách bài gần tâm; ngược lại "similarity to the centre" | chữ |
| — (RQ-04) | Khối CMI có ρ, 3 nhóm tertile, δ, p | "Not tested yet." + câu giải thích, không số (handoff §3.4) | cấu trúc |
| — | Hero chỉ có nhánh "Yes."; topic chỉ có "Above…" | Đủ nhánh trên / bằng / dưới median cho cả kênh lẫn topic (câu ở mục "Chữ landing" bên dưới) | chữ |
| — | "ruff · mypy strict · pytest · 7 pre-commit gates" | Bỏ số "7" (số đếm tay dễ trôi) | chữ |
| UI-L20260903-landing-vs-app-routes | "Read the methodology" trỏ `#`; "View the repo" trỏ `#` | "See how it works" trỏ `#method` (chưa có trang methodology); bỏ nút repo tới khi có repo công khai | chữ |
| — | Trục strip cố định 0–5.6% | Biên phải = bài cao nhất + 0,2 điểm, làm tròn lên bội 0,2 (hôm nay vẫn 5.6). Rủi ro đã biết: 1 bài ngoại lai (VD bài mới, ít views ở snapshot đầu) kéo giãn trục và dồn mọi strip sang trái — chưa đặt ngưỡng cắt vì chưa có căn cứ | — |
| — | Chấm `#9AA3AE` (nay token `--chart-dot`) | Giữ màu mockup; chỉ đạt ~2,5:1 trên nền trắng, dưới mức 3:1 cho đồ hoạ mang nghĩa (vòng rỗng của nhiễu chỉ phân biệt bằng nét) — Claude Design chọn lại màu | cấu trúc |

### Chữ landing — Thy duyệt 2026-10-08 (agent `copy-reviewer`, 2 lượt)

Lý do chung: chữ của mockup dùng thuật ngữ và mẫu số trước khi định nghĩa, dồn nhiều số vào một câu, và có câu nói
quá dữ liệu. Code đã đổi theo bản dưới; **mockup nên lấy đúng câu này**. Số trong câu sinh từ API.

- (Thay bởi mục ADR-0032 cuối file cho hero / Approach / Problem Q1 / CTA — landing dùng "content units".)
- **Hero**: câu phụ "Unthreaded shows how each post on a Threads channel did compared with the rest of that channel,
  not with Threads as a whole. Every figure says how many posts it rests on." · **dải thống kê mới** giữa 2 nút và panel
  (posts since <tháng bài đầu> · with recorded views · median engagement rate · topics · "Data as of <ngày>") · câu
  hỏi 'Did "8 kinh nghiệm sau 8 năm ở Pháp" (8 lessons from 8 years in France) do better than the channel's usual
  post?' · trả lời "Yes. Its engagement rate is higher than X% of the channel's other posts." + dòng "Engagement rate:
  likes, replies, reposts and quotes per 100 views." (dưới median: "Not this time… higher than only X%…"; bằng: "About
  usual: it sits at the channel median.") · chế độ topic "Yes, within its topic too: higher than A of the other B
  "<topic>" posts." · nút "All posts · N" / "Same topic · N" · nhãn chấm "higher than A of the other B" · nhãn trục
  "middle half a–b%" (IQR chỉ trong khối Method) · "6 of 152 excluded: no views recorded" · nút phụ "See how it works".
- **Problem**: Q1 Missing "A reference point: a 3% engagement rate means little until you know what is usual for this
  channel." · Q2 Missing "Topics found in the text itself, even though posts mix Vietnamese, French and English." · Q3
  "Has the channel already answered this somewhere?" / "One place to search the posts and the answers to followers, by
  meaning as well as keywords." (không nói follower hỏi lặp lại — chưa có dữ liệu, ADR-0007).
- **Approach** (eyebrow "02 · Approach"): "Three layers, one per question, built on the same data." / "Follow the post
  above through all three. Layer 2's topics become layer 1's comparison groups, and each post's text, tagged with its
  topic, becomes what layer 3 searches." · thanh input "the post plus the author's follow-up parts, rebuilt from reply
  links" · Measure "Each post's engagement rate is placed among all the channel's posts, with the median, the middle
  half and the post count shown." · Search "…searched by keyword and by meaning. It will be scored on a test set of real
  questions once a privacy decision is made."
- **Proof** (eyebrow "03 · Proof"): "What the data already answers, and what it doesn't yet." · panel 2 trả lời
  "Partly. A of the N posts with text fall into K topics; the other M fit none and stay unclustered." · 2 dòng loại gộp
  thành "6 of 152 posts have no text to embed; the same 6 have no recorded views." **chỉ khi** code kiểm thấy 2 tập
  trùng nhau (khác thì giữ 2 dòng, UI-0011-two-exclusions) · Limits "Topics with fewer than <min_posts_to_compare>
  posts with recorded views are faded…" (ngưỡng đọc từ API — một tên duy nhất cho cờ: "too few posts to interpret" — Thy đổi 2026-10-09, ADR-0023, dùng chung landing + app) ·
  CMI "(roughly, how much of it is in languages other than its main one)… still open: no number appears here until it
  is tested with an effect size and Holm correction."
- **How it works**: node Knowledge base "It will be scored on a test set of real questions, once a privacy decision is
  made, before any chatbot is built on top." · "gate (provisional)" (ngưỡng tạm theo `docs/roadmap.md`).
- **About**: bỏ chip 9 topic (đã có ở 2 panel) · dòng số "152 posts · 681 answers to followers · 367 follow-up parts ·
  350 replies on other accounts · …".
- **CTA / footer**: "Every post, measured against its own channel." / "The dashboard reads the same data as this page,
  with every topic and the method behind each number." · footer "Data as of <ngày>".

Giữ nguyên: tagline "The algorithm, read back to you." (UI-0009-tagline), "named by Claude", "validity_index (DBCV)".

### Việc 3 — kiểm định theo topic lên landing, sàn views ở Analytics (Thy duyệt 2026-10-09, `copy-reviewer` 1 lượt)

Code đọc `GET /topics/comparisons` (tính trong job NLP sau mỗi lần gom cụm) và `views_floor` của `/analytics/overview`.
Mockup nên lấy đúng các câu dưới; số trong câu sinh từ API (`UI-0023-comparison-test`, `-holm-family`, `-stale-tests`,
`-views-floor`).

- **Panel 1** — **Đã thay bởi mục "ADR-0024" bên dưới (2026-10-18)** cho dòng trả lời, dòng phụ, hover, Limits; câu
  cũ giữ lại để đối chiếu. Câu hỏi "Which topics get a higher engagement rate than the rest of the channel?" (thay câu duyệt
  2026-10-08: phép so là *tỉ lệ*, so với *phần còn lại*) · pill `live` khi có kết quả · trả lời "Posts on <topic> tend
  to get a higher engagement rate than the rest of the channel." (nhiều topic nối "A, B and C"; có topic thấp hơn: "…;
  posts on <C> tend to get a lower one."; không topic nào: "No topic's engagement rate can be told apart from the rest
  of the channel after correcting for multiple comparisons.") · dòng dưới "Each topic is compared with every other post,
  unclustered ones included. p-values are corrected for all 27 tests: 9 topics × engagement, share rate and
  conversation. Tests ran <ngày> at <giờ> on data collected up to <giờ> (Paris time); the medians and dots (one per
  post) use the latest data." · cột "δ" (tooltip "Cliff's delta, from −1 to +1") và "Holm p" · ghi chú mặc định thêm
  "δ runs from −1 to +1: above 0, the topic's posts tend to have a higher rate than the rest of the channel." · hover:
  "Its posts tend to get a higher rate than the rest of the channel: one of its posts beats a randomly picked other
  post 81% of the time (Cliff's δ +0.62, 95% CI +0.43 to +0.81, unadjusted; Holm-corrected p 0.002)." / "Not
  distinguishable from the rest of the channel after correction (…)" / "Too few posts to draw a conclusion; read as
  indicative only (…)" · Method định nghĩa δ, "(1 + δ) / 2 … ties counted as half", "two-sided", "95% CI from
  inverting the same permutation test, unadjusted", "across 27 tests (9 topics × …)" — chưa nói "Topics page" vì trang
  đó chưa hiện kiểm định · Limits thêm "Medians describe; only the test decides higher or lower. The CI is unadjusted,
  so it can exclude 0 while the corrected p stays above 0.05. Holm-corrected p-values are capped at 1." · kết quả
  thuộc lần gom cụm cũ: ô "—", câu "Effect sizes and p-values are hidden: topics were re-clustered after the last tests
  ran (…), so those results describe an older grouping of posts. They return once the tests are rerun on the current
  topics."
- **Approach, lớp 1** — "…with the median, the middle half and the post count shown. Each topic is then compared with
  the rest of the channel, with an effect size and a corrected p-value." (bỏ "Comparing groups with an effect size is
  next.").
- **How it works** — node API: "…Per-topic tests (each topic against the rest of the channel) run in the daily NLP job
  right after clustering; the API only reads the stored results." · stack "median/IQR on request · per topic,
  precomputed daily: Brunner-Munzel permutation test, Cliff's δ (95% CI), Holm correction" · node SQLite "…every
  clustering run with its parameters, scores and per-topic test results." + bảng `topic_comparisons` · node Cluster
  thêm dòng "tests: each topic vs the rest: Brunner-Munzel permutation, daily after clustering" (Thy chọn dòng stack,
  không thêm node).
- **Analytics, bảng top** — "Only posts with at least 1,901 views are ranked: below that, a few reactions move a rate
  too much for a fair comparison. The cut-off is the 25th percentile of views among posts with recorded views,
  recomputed as new views come in; 37 of 146 posts fall below it." (thay câu "Ranked by rate, so a post with few views
  can reach the top by chance…").

### ADR-0024 — so sánh topic dạng khám phá (Thy duyệt 2026-10-18, `copy-reviewer` 1 lượt)

Kết quả đạt p Holm chưa bền qua các cách chia cụm → là **gợi ý, chưa phải kết luận** cho tới khi RQ-01 chọn luật bền
(`UI-0024-exploratory-comparisons`). Mockup nên lấy đúng các câu dưới (số và tên sinh từ API); luật
`ADR0024-topic-claim` cảnh báo mọi câu "tend to get a higher / lower …".

- **Câu hỏi panel 1 giữ nguyên có chủ đích** (Thy chọn; landing đổi 2026-11-01 sang "Does any topic's engagement rate
  differ from the rest of the channel?" — ADR-0032): "Which topics get a higher engagement rate than the rest of
  the channel?" — câu hỏi hợp lệ; dòng trả lời mang ý tạm thời.
- **Dòng trả lời (đậm):** "For now, one topic stands out above the rest of the channel: <topic>." · nhiều topic: "For
  now, 2 topics stand out above the rest of the channel: <A> and <B>." · chỉ thấp hơn: "…stands out below the rest of
  the channel: <C>." · cả hai chiều (Thy đổi 2026-10-18 để tên luôn sau dấu hai chấm): "For now, 3 topics stand out from the rest of the
  channel: <A> and <B> above it; <C> below it." (dấu chấm phẩy: danh sách 3+ tên đã có dấu phẩy bên trong)
  · không topic nào: "For now, no topic's engagement rate can be told apart from the rest of the channel after
  correcting for multiple comparisons." — tên topic đặt sau dấu hai chấm (tên do Claude đặt, hay mở đầu bằng động từ
  "-ing", làm chủ ngữ sẽ đọc nhầm).
- **Dòng phụ:** khi có topic được nêu tên, câu đầu là "This is a lead, not a finding: it holds for the current topics,
  which are re-clustered as new posts arrive." rồi mới tới "Each topic is compared with every other post…".
- **Hover topic được nêu tên:** "A random post from this topic beats a random post from the rest of the channel 80% of
  the time (Cliff's δ +0.60, 95% CI +0.39 to +0.81, unadjusted; Holm-corrected p < 0.001). A lead in the current
  topics, not a finding yet." (bỏ "one of its posts" — đọc như 1 bài cụ thể).
- **Limits:** "A topic is named in the answer above only when its Holm-corrected p is below 0.05 and it has at least 5
  posts with recorded views; smaller topics are faded and read as indicative only. Medians only describe; the test
  alone decides which topics are named. Every comparison here is exploratory: it depends on where the topic boundaries
  fall. Topics are re-clustered daily with a fixed random seed, so the same posts give the same topics, but a few new
  posts or a different seed can redraw them. [câu "Re-running the tests on earlier groupings…" — Thy thay 2026-10-20,
  xem mục dưới] A topic will be reported as a finding only once it passes a stability rule (re-clustering with several
  random seeds); that rule is not set yet." + phần CI / Holm / "not distinguishable" giữ nguyên.
- **Thuật ngữ trên lớp chính:** "topics" + "re-clustered"; từ 2026-10-20 chỉ dùng "clustering" (bỏ "grouping"), định
  nghĩa trong Method; "exploratory" chỉ trong Limits (kèm định nghĩa).
- **Mockup còn câu kết luận dạng khác** mà regex `ADR0024-topic-claim` không bắt: `src/dashboard/mockups/landing.dc.html`
  "`N of T topics differ from the rest of the channel after correction.`" — Claude Design đổi theo dòng trả lời ở trên
  ("For now, … stands out …").
- **Không ghi số 0/2/0/1/1 lên UI** (nghiên cứu một lần, không có API) — số sống là cột "stood out in" (mục dưới).
- **Yêu cầu thiết kế (Thy chọn 2026-10-18): đánh dấu cả topic THẤP hơn kênh.** Hiện chỉ topic cao hơn được tô amber
  (`src/dashboard/src/components/LandingProof.tsx` — `highlighted`); design system chưa có token cho "thấp hơn" nên
  Claude Code không tự chọn màu. Claude Design: đề xuất kiểu đánh dấu (màu/biểu tượng, đạt AA) trong mockup + token
  trong `design-system.md`; tới lúc đó topic thấp hơn chỉ được nêu tên ở dòng trả lời. Khi có kiểu đánh dấu, Limits có
  thể thêm "topics named above or below are highlighted".

### ADR-0024 — lịch sử "k of m" (Thy duyệt 2026-10-20, `copy-reviewer` 1 lượt + sửa theo `code-reviewer`)

`UI-0024-partition-history`: cột mới cạnh "Holm p" ở panel 1 (code: `LandingProof.tsx`, câu hover ở `historySentence`,
`src/dashboard/src/lib/landing.ts`; hướng + k từ API `history.direction` / `stood_out`). Bản nháp "passed in k of the
last m clusterings" bị thay vì "passed" đụng chữ "passes a stability rule" và đứng cạnh câu trả lời "no topic … can be
told apart"; "stood out" dùng lại đúng từ của dòng trả lời. Mockup Topics/landing lấy đúng các câu dưới (số từ API).

- **Tên cột:** "stood out in" (khi chưa có kiểm định: "stood out in · next"); tooltip: "Clusterings in which this
  topic stood out, out of those with enough of its posts to test. See Method and limits."
- **Ô:** "2 of 3 ↑" (↓ = thấp hơn kênh); k = 0 → "0 of 5", không mũi tên; "—" khi m = 0. Mũi tên bắt buộc: thiếu
  hướng, topic thấp hơn sẽ đọc thành "cao hơn" dưới câu hỏi "higher…". Screen reader: "stood out above the rest of
  the channel in 2 of 3 clusterings" · k = 0: "stood out in 0 of 5 clusterings" · m = 0: "no clustering had enough of
  its posts to test yet".
- **Hover (nối sau câu kiểm định):** "Since 2026-10-12, this topic has been tested on 4 clusterings: it stood out
  above the rest of the channel in 2 of the 3 with enough of its posts to test, but not in the current one." (4 = số
  cách chia ĐÃ kiểm định topic — không viết "the posts have been clustered N ways": bước so sánh có thể lỗi suốt 1
  cách chia; đuôi "including the current one" khi lần hiện tại đạt — đạt cả hai hướng thì thêm "(above)"/"(below)";
  "; the current one had too few of its posts to test" khi thiếu bài; bỏ hẳn khi `stale`; không có cách chia thiếu bài
  → "in 2 of them") · cả hai hướng: "…stood out above the rest of the channel in 2 and below it in 1 of the 3 …" · k =
  0: "Since 2026-10-09, this topic has been tested on 5 clusterings and did not stand out in any of them." · k = 0 có
  cách chia thiếu bài: "Since 2026-10-17, this topic has been tested on 3 clusterings; it had enough posts to test in
  2 and stood out in none." · 1 cách chia: "Since 2026-10-20, this topic has been tested on one clustering and did not
  stand out in it." / "…and stood out above the rest of the channel in it." · m = 1 có cách chia thiếu bài và đã
  đạt: "Since 2026-10-19, this topic has been tested on 2 clusterings: it stood out above the rest of the channel in
  the only one with enough of its posts to test, the current one." (không "in 1 of the 1") · m = 0: "Since 2026-10-17, this topic has
  never had enough posts to test."
- **Limits — câu 2026-10-18 chỉ đổi 1 từ:** "Re-running the tests on earlier clusterings of the same posts has made
  results appear and disappear." ("groupings" → "clusterings"; không gắn "the column shows this" — cột tính trên tập
  bài lớn dần, không phải cùng tập bài)
- **Limits — thêm sau "that rule is not set yet.":** "The "stood out in" column is a record, not that rule. A
  clustering is one way of grouping the posts into topics; daily runs that give the same topics count once, using the
  latest test. The column counts the 5 clusterings tested since 2026-10-09 and leaves out those that gave a topic too
  few posts to test; each topic's count starts at its first counted clustering. ↑ means above the rest of the channel,
  ↓ below; a topic that stood out both ways shows the direction of its current δ, or, while tests are hidden, the
  direction it stood out in more often. The clusterings share most of their
  posts, so they are not independent tests. Topics are matched across clusterings by their posts and content; when
  topics merge or split, the result may count as a new topic, and its count starts again." (không ghi "id" — chữ nội
  bộ, và sai một nửa với ADR-0018: phần giữ quá nửa bài khi tách vẫn giữ id)

### Việc 4 — trang /topics dựng lại (Thy duyệt bố cục + chữ 2026-10-29; `ux-reviewer` 7 lượt, `copy-reviewer` 2 lượt)

Thy bác 3 lần trước khi duyệt:
1. Lần 1: số trần, Method đóng, thiếu công thức.
2. Lần 2: tiêu đề nhỏ hơn nội dung.
3. Lần 3: khoảng trắng bên phải.

Luật trình bày đã chốt nằm ở `docs/claude/design-system.md` §3 (thang chữ chung cho mọi trang, ba lớp màu nền, nhấn chữ), §3b (sổ luật UI/UX) và §9 (bản đồ đa sắc). Mockup Topics phải theo đúng các câu dưới. Số liệu lấy từ API; nguyên văn từng câu nằm trong `src/dashboard/src/components/TopicsView.tsx`, `TopicComparisonTable.tsx`, `TopicMethods.tsx` và `AppEngagementPanel` trong `LandingProof.tsx`.

**Khung trang**
- Đầu trang căn giữa, theo thứ tự:
  - nhãn "TOPIC ANALYSIS";
  - h1 "Topic Explorer";
  - câu hỏi "What does the channel write about, and does any topic's engagement differ from the rest of the channel?";
  - 2 chip "clustered …" và "data as of …";
  - dải mục lục 6 khối.
- Mỗi khối gồm:
  - nhãn "NN · TÊN NGẮN" (cùng chữ với mục lục, `lib/topicSections.ts`);
  - h2;
  - 1 câu mục đích;
  - khung "ANSWER";
  - "What to know" + "Key numbers";
  - các mục h3;
  - "Method and limits" mở sẵn: "How it is computed" rồi "Limits", xếp dọc.

**Tên 6 khối** (tên ngắn → tiêu đề h2)
| # | Tên ngắn | Tiêu đề |
|---|---|---|
| 01 | How to read this page | How to read this page |
| 02 | Topics and map | What does the channel write about? |
| 03 | Engagement by topic | Does any topic's engagement rate differ from the rest of the channel? |
| 04 | All three rates | Does any topic differ from the rest of the channel in engagement, share or conversation rate? |
| 05 | Stability | How stable are these topics? |
| 06 | How it is computed | How every number on this page is computed |

**Nhãn kết quả** (`components/Verdict.tsx`, Thy chốt 2026-10-29)
- "▲ Stood out above" / "▼ Stood out below"
- "● Not significant after correction"
- "◌ Too few content units (n < 5): not concluded", đặt trong pill xám
- "— Not tested"

Bảng có chú giải "How to read the result column" ngay bên trên.

**Câu trả lời** (mẫu, số từ API)
- Khối 02: "11 topics cover 84 of the 162 content units in the latest clustering run (52%)."
- Khối 03: "For now, no topic large enough to conclude on has an engagement rate significantly different from the rest of the channel (corrected for all 33 tests)."
  - Câu này tách khỏi landing; landing giữ "can be told apart".
- Khối 04: "For now, no: none of the 27 tests on topics large enough to conclude (of 33 in all) has a corrected p below 0.05."
- Khối 05: "No stability rule is set yet, so a topic that stands out on this page is at most a lead, not a finding."

**Song ngữ**
- Bảng dùng cột "Topic (English)" (thay 2026-11-01, ADR-0031: tên topic tiếng Anh nằm trên chữ gốc, cùng ô — `UnitText`).
- Mỗi bài đại diện có dòng "Original language · topic: …" (thay 2026-11-01, ADR-0031: dòng "Topic: … · original
  language" nằm trên chữ gốc).
- Từ khoá ghi "Shown in the original language … The keywords are not translated; …".
- Tóm tắt tiếng Anh từng bài chờ ADR riêng (phương án A, Thy chốt 2026-10-29).

**Bản đồ topic**
- Đa sắc: 8 màu `--cat-1..8`, topic thứ 9 trở đi dùng hình thoi.
- Đặt bên trái, danh sách topic bên phải làm chú giải (`UI-L20261029-topic-categorical`).
- Landing vẫn một màu nhấn (đến 2026-11-01; từ đó landing dùng bản đồ nhiều màu của /topics — ADR-0032).

**ADR-0026 (logo):** `src/dashboard/mockups/landing.dc.html` dòng 24, 40-41 còn navbar logo tĩnh 28px và hero
bản động lặp (`picture` + công tắc `animatedLogo`) — đổi sang logo phát lại mỗi 15 giây ở navbar và hero (Claude
Design sửa mockup; code đã theo `UI-0026-logo-replay`).

### Ghi chú cho vòng thiết kế kế tiếp

1. **Dữ liệu landing:** API đã trả bài gần tâm, từ khoá, `run_at`, DBCV (`validity_index`), 2 ARI, nhiễu và cờ n nhỏ
   theo topic (`/topics`, `/pipeline/summary`, PR 10), và từ Việc 3 (2026-10-09) δ + CI + p Holm theo topic × 3 chỉ số
   (`/topics/comparisons`). Còn thiếu: CMI theo engagement (RQ-04). Lần gom cụm mới nhất lúc audit vòng 3 (2026-10-07, `cluster_runs.id = 7`) có số khác mockup:
   nhiễu 41,1%, validity_index (DBCV) 0,261 — mockup sẽ đổi số khi có file xuất (Việc 4).
2. **Chưa audit theo hợp đồng** `overview-amber.dc.html`, `overview-cyan.dc.html`, `design-system.dc.html`,
   `docs/design/layout-tiers.dc.html` — ngoài cảnh báo tự động ở mục 1. Làm khi các mockup đó vào vòng port.
   `design-system.dc.html` ghi màu Blue cho "follower geography": dữ liệu đó chưa có trong DB hay API — chỉ là ý nghĩa
   màu, không phải lời hứa tính năng.
3. **Claude Code đã sửa trong tài liệu của Claude Design (dữ kiện kỹ thuật):** 2026-10-06 — `landing-handoff.md`
   `src/main.py:258` → `:270`, 4 chỗ "chờ Câu hỏi mở" → id hợp đồng; `topics-brief-for-claude-code.md` 2 dòng "Câu hỏi <!-- consistency: allow ref-anchor — ghi lại tham chiếu cũ trước khi sửa -->
   mở 1 / 2" → "Đã chốt"; `brief-ui-contract-review-2026-10-06.md` gắn `consistency: allow ADR0001-coming-soon`.
   2026-10-07 — `landing-handoff.md` §0.5 dòng UI-0017-run-time: thêm `run_at` thật (`cluster_runs.id = 3`); PR 10 —
   `landing-handoff.md` §0 (bảng A, B) và §4: trường đã có API trỏ tới `/topics`, `/pipeline/summary`;
   `docs/claude/design-system.md` §2.1 thêm token `--chart-dot` / `--chart-dot-faint` (2 màu chấm mockup landing đang
   dùng mà §2 chưa có) — mockup nên gọi đúng tên token này.
   2026-10-09 (ADR-0023) — `topics-proposal.md` §2: engine so sánh là Brunner-Munzel (không còn Mann-Whitney), họ
   Holm 27 phép so (không còn 9); §1 bảng trường: engine Brunner-Munzel, `holm_adjust` đã có, nhóm so sánh đã
   chốt. `landing-handoff.md` §4 dòng δ/Holm: "chưa có API — Việc 3"; §0 bảng A dòng "Cliff's δ, p, p Holm": việc repo đã làm/còn thiếu, ghi chú họ 27; ref `src/main.py:270` → `:302`. `topics-brief-for-claude-code.md` Việc 1: <!-- consistency: allow ref-anchor — ghi lại tham chiếu cũ trước khi sửa -->
   ghi chú "đã chốt ở ADR-0023" (1a–1f + 1h), Việc 3: `holm_adjust` đã có.
4. **Tầng reach (ADR-0012)** chưa có trên mockup nào: `UI-0012-reach-tiers`, `UI-0012-raw-views-reference`,
   `UI-0012-not-tiered` là ràng buộc cho lần thiết kế Analytics / Topics tới; mốc so sánh mô tả là "the channel's recent
   level (median of up to 20 prior posts)" (hạn chế cửa sổ 20 bài: `docs/claude/data-model.md`).
5. **(Đã chốt bởi ADR-0023, 2026-10-09)** Nhóm so sánh theo topic = phần còn lại của kênh, gồm bài nhiễu; kiểm định
   Brunner-Munzel hoán vị, số chính là Cliff's δ kèm CI ghi "unadjusted"; chỉ khẳng định khi p Holm < 0.05 trong họ
   mọi phép so của trang Topics (9 topic × 3 chỉ số) **và** — từ ADR-0024 (2026-10-18) — qua luật bền qua các cách
   chia cụm (chưa có luật nên hiện chưa có câu khẳng định; xem mục ADR-0024) — landing dùng đúng p Holm đó, không có họ riêng 9 phép so;
   topic n < `min_posts_to_compare` không kết luận. Mean không hiện ở đâu trên UI (median + IQR + n; IQR có
   tooltip "interquartile range: the range the middle 50% of posts fall in"; n = 0 → "—").
   Mockup landing còn ghi "Mann-Whitney U … Holm across 9 tests" và "Mann-Whitney U + Cliff's δ + bootstrap CI" (cảnh <!-- consistency: allow ADR0023-old-test-engine — trích nguyên văn mockup để Claude Design sửa -->
   báo `ADR0023-old-test-engine`) — đổi theo câu mới trong code (`LandingProof.tsx`, `LandingTechStack.tsx`).
6. **(Đã sửa bởi ADR-0022, 2026-10-08 — từ khoá mới có sau khi merge + lần gom cụm kế tiếp)** **Từ khoá c-TF-IDF còn lẫn stopword tiếng Việt** ("một", "điều", "tui", "tớ", "ko"…) — lỗi phương pháp, không phải
   chữ; Thy chọn sửa bằng ADR + PR riêng trước khi công khai trang (2026-10-08). Mockup đừng chép bộ từ khoá hiện tại.

### ADR-0031 — Overview và Analytics theo khuôn khối của Topics (2026-10-31 → 2026-11-01; `ux-reviewer` 4 lượt, `copy-reviewer` 4 lượt)

- Mockup `overview-amber.dc.html` và `overview-cyan.dc.html` còn ghi "root posts in window" ở dải KPI (cảnh báo
  `ADR0031-old-app-copy`). Code đã bỏ dải KPI (số của cửa sổ nằm ở dải hero + hộp Key numbers của khối 01) và dùng một
  tên "content units" có định nghĩa dưới câu hỏi đầu trang. Vòng thiết kế kế tiếp: dựng lại mockup Overview theo 3 khối
  01 cửa sổ → 02 nhiều views nhất → 03 các chỉ số (`UI-0031-page-shape`).
- **Thy duyệt chữ cuối 2026-11-01** (PR 2a, "OK commit" sau khi xem 3 trang trên localhost). Mockup theo đúng các câu:
  - Câu hỏi Overview: "How did the channel perform in the time window you choose, and which content units published in
    it drew the most views?"; Analytics: "Which content units have the highest rates per 100 views, and how does
    engagement rate vary with posting hour and weekday?".
  - Eyebrow: "MEASURE · ONE TIME WINDOW", "MEASURE · RANKINGS AND POSTING TIME", "GROUP · TOPICS FROM TEXT".
  - Định nghĩa dưới câu hỏi: "A content unit is one post as published, plus the follow-up parts its author added in the
    same thread; comments are left out. Each rate counts interactions per 100 views of a content unit's opening post
    (its first post)." (giữ "comments are left out" — Thy: phần nối tiếp của tác giả thuộc content unit, bình luận của
    người khác thì không; không mâu thuẫn với conversation rate).
  - Câu trả lời Overview 01: "Content units published from <date> to <date> have a median engagement rate of X%; across
    all content units collected so far, it is Y% (not tested)." + gạch đầu dòng "All content units collected so far:
    median Y%, middle half a–b% (IQR), n = N. This window is part of that set, and the gap between the two medians has
    not been tested, so it does not show a better or worse period." Mẫu nhỏ: "(n = N, too few content units to
    interpret)", bỏ vế so với kênh.
  - Limits Overview: "…so numbers can be up to a day old; the time at the top of the page says when they were last
    read."
  - Dòng ngữ cảnh trên chữ gốc: "Topic: X · original language" / "Unclustered: fits none of the N topics · original
    language"; bảng Topics: tiêu đề "Content unit: topic in English, then the first line as written".
  - Ghi chú median: "Middle half a–b% (IQR) · n = N content units with recorded views[ · too few content units to
    interpret]."; Holm: "Holm-corrected across all 39 tests; only topics with at least 5 content units with recorded
    views can count."; chú giải heatmap: "no n: no content unit published then".
  - Ngày trong thân trang "Oct 2, 2026" (+ ", 9:08 PM"); ISO chỉ ở chip "data as of".

### ADR-0032 — Landing dùng lại khối của trang app (2026-11-01; `ux-reviewer` 3 lượt, `copy-reviewer` 2 lượt)

- Mockup `landing.dc.html` lệch code ở nhiều chỗ (vòng thiết kế kế tiếp dựng lại theo `UI-0032-*`): panel hero có tiêu đề
  là câu hỏi + khung ANSWER, không hộp Key numbers, nút "Compare with"; Problem 3 cột; Proof = 3 khối của /topics (bản
  đồ 3D nhiều màu, mục lục 3 khối); sơ đồ "How it works" 960px; một tên "content units" trên cả landing; CTA "Every
  content unit, measured against its own channel." + nút 2 "Explore all topics" → /topics.
- **Thy chốt chữ 2026-11-01** (qua câu hỏi trong PR 2b; câu cuối duyệt cùng lúc OK commit):
  - Câu dẫn hero: "Unthreaded shows how each content unit on a Threads channel did compared with the rest of that
    channel, not with Threads as a whole. Every figure says how many content units it rests on." + định nghĩa
    `CONTENT_UNIT` ngay dưới (trước 2 nút).
  - Panel hero: tiêu đề 'Did "8 kinh nghiệm sau 8 năm ở Pháp" (8 lessons from 8 years in France) do better than the
    channel's usual content unit?' (giữ ngoặc kép — tên gọi của bài); mục đích "Ranks this content unit against the
    channel's other content units by engagement rate: likes, replies, reposts and quotes per 100 views of its opening
    post."; bước Rank "Yes means its rate is above the median. The percentage counts the other content units with a
    lower rate (ties not counted), as a share of all the others, rounded down."
  - Problem Q1: "Which content units did well by this channel's own standard?"
  - Panel engagement của landing: câu hỏi "Does any topic's engagement rate differ from the rest of the channel?"
    (thay "Which topics get a higher engagement rate than the rest of the channel?").
  - Ghi chú ARI (panel độ bền, cả /topics): "On content units with a topic in both runs. 1 = identical grouping. Same
    seed every run, so 1.00 shows reproducibility, not stability."

### ADR-0034 — nhãn ngày của chuỗi views theo ngày (Thy duyệt 2026-11-01 cùng OK commit PR #34; `ux-reviewer` + `copy-reviewer`)

- Mockup chưa có các chữ dưới (vòng thiết kế kế tiếp theo `UI-0034-meta-day` + `UI-0034-paris-post-day`):
  - Phụ đề biểu đồ khối 01 Overview: "As Threads reports them: one total per day, with days in Pacific time."
  - Bước Method "Which day": "The Threads API gives the account's views only as one total per day, and its days run on
    Pacific time (California). So each chart day starts at midnight Pacific, which is 9 am in Paris for most of the
    year. A content unit falls in a window by the day it was published in Paris time: the date printed under it in
    block 02." + 3 dòng công thức: "chart day = calendar date in America/Los_Angeles", "content unit day = publish date
    in Europe/Paris", "unit in window when start ≤ content unit day ≤ end (start, end = chart days at the two handles)".
  - Limits: "A content unit published between midnight and 9 am Paris time (8 am for a few weeks a year) is counted on
    its Paris date, but the account's views from those first hours land on the chart day before. This only matters at
    the edges of a window." + câu đếm lúc chạy "So far, it applies to N of the M content units collected, with or
    without recorded views."
  - Ngày dưới mỗi bài ở khối 02: "Oct 2, 2026 · Paris time"; "What to know": "n = N content units with recorded views."
- PR nợ nhỏ sau ADR-0034 (`copy-reviewer` + `ux-reviewer` 2 lượt; Thy chọn 2026-11-02, câu cuối duyệt cùng OK commit):
  - Một động từ "Published" cho cột ngày đăng: /topics và /analytics cùng ghi "Published (Paris time)" (/analytics trước
    là "Posted (Paris time)"). Thẻ màn hẹp của /topics: "published Oct 2, 2026 · Paris time" (múi giờ sau ngày, như khối
    02 Overview). Tiêu đề bảng căn đáy (`align-bottom`) để tiêu đề 1 dòng và 2 dòng chung đường chân.
  - Heatmap /analytics, bước "Readable cells": "A cell is readable (coloured, and counted in the ranges at the top of this
    section) only when it rests on at least N content units, the same minimum every comparison on this dashboard uses. The
    colour scale runs only across those cells." (trước: "A cell is read only when…", dễ đọc thành "read-only" và sai — ô n < N
    vẫn có median trong hover và bảng). Công thức 3 dòng "n ≥ N → coloured" / "1 ≤ n < N → hatched" / "n = 0 → plain, no
    n" ("plain", không "grey": nền ô n = 0 gần trắng, ô sọc mới trông xám) (thay "readable ⇔ n ≥ N" — ký hiệu lạ với người không chuyên; 3 nhánh khớp `cellStyle` và 3 dòng chú giải).
    Còn mở (toàn sản phẩm, ux-reviewer 2026-11-02): `next/font` chỉ nạp bộ ký tự `latin` của IBM Plex Mono nên → ≤ ≥ ⇔
    (và các ký hiệu toán ở `/topics`) rơi xuống font dự phòng, rộng hơn ký tự mono khác.
  - Cùng khối, sửa câu sai sự thật có từ trước: "What to know" — "…are **hatched** instead of coloured; their median
    appears only in the hover text and the table below." (trước: "only in the table below", nhưng hover cũng hiện
    median); chú giải "too few content units (n < N): hatched, not coloured" (trước: "not coloured", lẫn với ô n = 0).
  - Bước "Median per cell": "n = their count" tách thành dòng công thức riêng (màn hẹp ngắt giữa biểu thức).
  - Một cách ghi múi giờ (Thy chọn 2026-11-02): tiêu đề bảng "(Paris time)", mọi dòng dữ liệu "<ngày> · Paris time" —
    gồm danh sách màn hẹp của /analytics: "6,365 views · May 14, 2026, 12:52 PM · Paris time". Chip "data as of … Paris
    time" và câu mốc kiểm định "(Paris time)" của landing không phải dòng dữ liệu, giữ nguyên.
  - Heatmap, ô n = 0 (sửa câu sai có từ trước, copy-reviewer 2026-11-02): chú giải "no n: no content units with
    recorded views in that hour or weekday" (trước: "no content unit published then" — sai khi giờ đó chỉ có bài chưa ghi
    được views, VD 08:00 Paris trên dữ liệu 2026-11-02); hover / aria "… · no content units with recorded views" (hằng
    `NO_POSTS` chung). Dòng dữ liệu /analytics màn hẹp giữ "· Paris time" thành một khối không ngắt (như /topics).
  - Khổ 320px (Thy chọn: sửa 2 chỗ tràn ngang, chưa thêm 320px vào máy đo): navbar landing thu khoảng cách + lề trong
    dưới `sm` (nút "View live dashboard" không còn tràn khỏi pill); thang màu heatmap xuống dòng (`flex-wrap`).

### Promise-audit 2026-11-02 — một content unit so với kênh, n của ARI, giờ gom cụm (Thy duyệt toàn bộ chữ 2026-11-02; `ux-reviewer` 3 lượt, `copy-reviewer` 2 lượt)

- Thy chọn 2026-11-02 (câu hỏi bật ra): khối mới 02 ở `/analytics` (giờ đăng thành 03); chọn bài bằng ô tìm kiếm + nút
  "Compare ↓" trên từng dòng bảng top (mang tỉ lệ của tab đang xem sang); so được cả 3 tỉ lệ (API `/topics` thêm
  `share_rate` + `conversation` theo topic); hộp Key numbers chỉ ở `/analytics` (panel hero landing giữ nguyên); link
  mới dưới panel hero landing tới `/analytics#unit`; nhiều bài trùng một giá trị (VD 37/163 bài share rate 0%) → cột vẽ
  gọn trong khung + nhãn đếm "37 content units at 0.000%" (phương án a, chiều cao biểu đồ giữ nguyên giữa 3 tỉ lệ).
- Mockup chưa có (vòng thiết kế kế tiếp):
  - Đầu trang `/analytics`: eyebrow "Measure · Rankings, one content unit, posting time"; câu hỏi "Which content units
    rank highest on each rate, how does any single content unit compare with the rest of the channel, and how does
    engagement rate vary with posting hour and weekday?".
  - Khối 02 "One content unit": tiêu đề "Did the content unit you pick do better than the channel's usual content
    unit?"; mục đích "Pick a content unit with recorded views. It is ranked on the rate you choose, against the rest of
    the channel or the rest of its own topic."; nhãn ô "Content unit to compare (N with recorded views, newest first)",
    gợi ý "Search first line or topic", không khớp "No content unit matches "…". Try a word from an English topic
    name."; "SELECTED CONTENT UNIT" + "Preselected: the example from the home page ("8 lessons from 8 years in
    France")."; 4 gạch "What to know" (tập đang so + nút đổi được gì · "Yes" = trên median · thứ hạng chỉ đếm bài thấp
    hơn hẳn · mô tả, không kiểm định); Key numbers 3 số (tỉ lệ của bài · "k of n other content units with a lower rate"
    + thanh "N% of the n others" · median + IQR + n của tập so); câu trả lời thêm nhánh "the highest in the channel",
    "the lowest in the channel, tied with N other content units", "higher than only k of the channel's n other content
    units" (thay "<1%"); Limits tách đôi ("…re-read every 4 hours while the collecting laptop is awake, so they are
    usually less than a day old." · "Newer content units have had less time…") + câu đếm số bài 0% cho share /
    conversation; bước Rank tách 3 câu, "strictly lower rate (equal rates do not count as lower)".
  - Khối 03: mục đích bắt đầu "All content units with recorded views, placed on a Paris or a Vietnam clock; …".
  - Landing: link "Compare any other content unit by engagement, share or conversation rate, on the Analytics page →";
    node "Dashboard · Landing" sửa câu sai kỹ thuật (promise-audit 2b): "Charts are hand-built in HTML/CSS; the
    daily-views chart on Overview and this diagram are SVG, and the 3D topic map uses Plotly (WebGL)." + stack
    "charts · HTML/CSS · SVG · Plotly (WebGL)" (trước: "Charts are hand-built SVG").
  - Khối độ bền (`/topics` + landing): "Clustered on <ngày> at <giờ> (Paris time), from the N content units that had
    text when it ran."; ghi chú ARI có n ("On the 110 content units with a topic in both runs." / "On the 163 content
    units present in both runs."), cảnh báo seed cho cả 2 ARI; DBCV "Weighted over all N content units; the M
    unclustered pull it toward 0." (bài unclustered chỉ vào mẫu số trọng số |t|/n).
- Cảnh báo mockup mới (ADR-0035, luật `ADR0035-old-chart-tech`): `src/dashboard/mockups/landing.dc.html:560#body` node
  "Dashboard · Landing" còn "Charts are hand-built SVG; the topic map uses Plotly." — vòng thiết kế kế tiếp đổi theo câu
  đã duyệt ở trên (biểu đồ HTML/CSS; SVG chỉ cho biểu đồ views theo ngày và sơ đồ; bản đồ 3D Plotly WebGL).

### Promise-audit 2026-11-02 gói 4 — 2 chữ cũ trong ruột (Thy duyệt 2026-11-04)

- Bảng công thức `/topics`, mục "Content unit": bỏ câu cuối "The landing page calls a content unit a “post”." — sai
  từ ADR-0032 (landing dùng chung tên "content units").
- Trạng thái rỗng `/topics` + landing panel Proof (lần gom cụm không ra topic nào), một helper `noTopicsSentence`:
  "The latest clustering run found no topics: none of its N content units grouped densely enough with others, so all of
  them stay unclustered." (N = `n_units` của lần gom cụm; trước: "…every content unit was left as noise" ở `/topics`,
  "…left unclustered" ở landing). Thy chọn bản có n + nguyên nhân (copy-reviewer); "noise" là từ riêng của HDBSCAN.
- Bảng công thức `/topics`, mục DBCV: "…Unclustered content units count in the total with weight 0, so a large
  unclustered share pulls the score toward 0." (trước: "a lot of noise lowers the score" — sai khi điểm âm: trọng số
  0 kéo điểm về 0, không luôn hạ; code-reviewer 2026-11-04) — cùng cách nói "toward 0" với khối Stability.
- Lỗi tải `/topics`: dùng `LoadError` chung (câu "The data service is not reachable right now." + nút "Try again" 44px,
  thử lại = tải lại dữ liệu server của trang) thay link gạch chân tự viết; chữ trạng thái rỗng theo thang `body` 15px
  (ux-reviewer 2026-11-04: C2, C3, T1).

### ADR-0036 — luật bền chốt trước RQ-01 (Thy duyệt bộ chữ cuối 2026-11-04, sau 3 vòng `copy-reviewer` / `ux-reviewer` / `code-reviewer`)

- Khối Stability (`/topics` khối 05, landing panel 03), câu trả lời: "Stability across random seeds is not measured yet,
  so a topic that stands out on this page is at most a lead, not a finding." (trước: "No stability rule is set yet, so …").
- Gạch đầu dòng: "The rule a lead must pass is **fixed in advance**: it must hold on reruns with other random seeds and a
  few content units left out. Those reruns have not been done yet." (trước: "The rule will come from …").
- Hàng "Stability across random seeds" (Thy giữ tên): "Re-clustering the content units with other seeds, a few left out
  each time, measures how much the topics depend on chance and on small changes in the data. A result becomes a finding
  only if it passes a rule fixed in advance on those reruns." — "rule fixed in advance" là link tới "Lead vs finding".
- Limits khối 01 `/topics`: "…measuring that is planned, and the reruns have not been done yet (see the stability block
  below)." · bảng công thức, "Random seed": "…measuring that (stability across seeds) is planned: the rule is fixed in
  advance and the reruns have not been done yet." (trước: "… is still research").
- Landing panel Proof, Limits: "A result becomes a finding only after it passes **a stability rule across random seeds**.
  That rule is fixed in advance, but it has not been applied yet: the reruns with other seeds have not been done."
- Khối Stability, Limits: "Comparing with the previous run mixes two changes: new content units, and the re-drawing they
  cause. The planned reruns separate them: some keep the same content units with other seeds (chance alone), others also
  leave 3% out at random (small changes in the data). They have not been done yet." (trước: "… would measure the chance
  part alone (same content units, other seeds); it is not measured yet.")
- Bảng công thức, "Lead vs finding" (plain + formula + where): "A lead is a result marked ▲ or ▼ on today's topics:
  corrected p below 0.05 with enough content units to test. A finding is a lead that also passes a stability rule fixed in
  advance. The reruns that apply the rule have not been done yet, so a result here is at most a lead." · công thức
  "finding = lead today and kept in ≥ 75 of K = 100 reruns" · "J(t, c) = |t ∩ c| ÷ |(t ∩ S) ∪ c|" · "found again: max over
  c of J(t, c) > 0.5" · "Rerun: today's content units clustered again with another UMAP seed and a shuffled order, with 3%
  of them left out at random." · "t: today's topic; c: a topic of the rerun; S: the content units kept in that rerun; |·|:
  number of content units; J: Jaccard overlap, 0.5 being the convention of the R package fpc (clusterboot). Unclustered
  is not a topic." · "Kept: the topic is found again (J above 0.5), has enough content units to
  test, and stands out again with corrected p below 0.05 in the same direction (▲ or ▼)." · "A rerun where the topic is
  missing or cannot be tested counts as not kept; the count is always out of 100."
