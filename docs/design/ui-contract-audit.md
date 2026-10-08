# Audit mockup theo hợp đồng UI

> Kiểm 2026-10-07 (vòng 3) trên gói Claude Design 2026-10-07, theo `docs/design/ui-contract.md` (Cập nhật tới: ADR-0020;
> gồm luật ADR-0012).
> **Người đọc:** Claude Design (sửa mockup ở vòng kế tiếp) và Claude Code (khi port). Claude Code **không sửa mockup**
> (ADR-0020). Số liệu cũ trong mockup (số bài, %, median…) không nằm trong audit này — xử lý riêng khi có file xuất
> (brief Việc 4).
> **Mức:** `cấu trúc` = phải đổi component / trạng thái / dạng dữ liệu / luồng; `chữ` = chỉ đổi câu chữ.

## 1. Cảnh báo tự động của sổ luật

Nguồn: `uv run python -m scripts.consistency.check --all` — mục "Cảnh báo mockup" (không chặn commit). Hook đầu phiên
in số cảnh báo; khi về 0, hàng này xoá. Hiện: **3** (1 báo nhầm + 2 theo ADR-0021). 8 cảnh báo ADR-0012 của vòng 2
đã hết.

| File mockup | Dòng | Luật | Khớp | Xử lý |
|---|---|---|---|---|
| `src/dashboard/mockups/landing.dc.html` | 533 | `ADR0001-coming-soon` | "sắp có" | **Báo nhầm**: nội dung bài gốc tiếng Việt dùng làm dữ liệu mẫu, không phải nhãn trạng thái. Hết khi mockup lấy dữ liệu từ file xuất <!-- consistency: allow ADR0001-coming-soon --> |
| `src/dashboard/mockups/overview-amber.dc.html` | 30 | `ADR0021-placeholder-logo` | logo giữ chỗ bằng icon "at" trong vòng tròn amber | `../public/brand/unthreaded-lockup.svg` cao 28px, tagline chữ HTML bên dưới (`UI-0021-logo-placement`) |
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
| UI-L20260903-stack-real-status | Panel 1 điền δ, p Holm, câu "None clearly…" và "computed offline from the 2026-10-01 snapshot" | Median/IQR/n theo topic là số thật (`TopicOut.engagement`); cột δ và p Holm hiện "—" kèm pill `next`; câu trả lời "<topic> has the highest median engagement rate among topics with enough posts to compare: X, against Y for the channel. The gap is not tested yet." (vế "among…" chỉ khi có topic mang cờ `insufficient_data`); cột "δ · next", "p, Holm · next"; dòng Preview: "medians and spread are live, Cliff's δ and Holm-corrected p-values are next" | chữ |
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
  posts with recorded views are faded…" (ngưỡng đọc từ API — một tên duy nhất cho cờ: "too few posts to compare") ·
  CMI "(roughly, how much of it is in languages other than its main one)… still open: no number appears here until it
  is tested with an effect size and Holm correction."
- **How it works**: node Knowledge base "It will be scored on a test set of real questions, once a privacy decision is
  made, before any chatbot is built on top." · "gate (provisional)" (ngưỡng tạm theo `docs/roadmap.md`).
- **About**: bỏ chip 9 topic (đã có ở 2 panel) · dòng số "152 posts · 681 answers to followers · 367 follow-up parts ·
  350 replies on other accounts · …".
- **CTA / footer**: "Every post, measured against its own channel." / "The dashboard reads the same data as this page,
  with every topic and the method behind each number." · footer "Data as of <ngày>".

Giữ nguyên: tagline "The algorithm, read back to you." (UI-0009-tagline), "named by Claude", "validity_index (DBCV)".

### Ghi chú cho vòng thiết kế kế tiếp

1. **Dữ liệu landing:** API đã trả bài gần tâm, từ khoá, `run_at`, DBCV (`validity_index`), 2 ARI, nhiễu và cờ n nhỏ
   theo topic (`/topics`, `/pipeline/summary`, PR 10). Còn thiếu: δ + p Holm theo topic (chờ Việc 1b chốt nhóm so
   sánh), CMI theo engagement (RQ-04). Lần gom cụm mới nhất (2026-10-07, `cluster_runs.id = 7`) có số khác mockup:
   nhiễu 41,1%, validity_index (DBCV) 0,261 — mockup sẽ đổi số khi có file xuất (Việc 4).
2. **Chưa audit theo hợp đồng** `overview-amber.dc.html`, `overview-cyan.dc.html`, `design-system.dc.html`,
   `docs/design/layout-tiers.dc.html` — ngoài cảnh báo tự động ở mục 1. Làm khi các mockup đó vào vòng port.
   `design-system.dc.html` ghi màu Blue cho "follower geography": dữ liệu đó chưa có trong DB hay API — chỉ là ý nghĩa
   màu, không phải lời hứa tính năng.
3. **Claude Code đã sửa trong tài liệu của Claude Design (dữ kiện kỹ thuật):** 2026-10-06 — `landing-handoff.md`
   `src/main.py:258` → `:270`, 4 chỗ "chờ Câu hỏi mở" → id hợp đồng; `topics-brief-for-claude-code.md` 2 dòng "Câu hỏi
   mở 1 / 2" → "Đã chốt"; `brief-ui-contract-review-2026-10-06.md` gắn `consistency: allow ADR0001-coming-soon`.
   2026-10-07 — `landing-handoff.md` §0.5 dòng UI-0017-run-time: thêm `run_at` thật (`cluster_runs.id = 3`); PR 10 —
   `landing-handoff.md` §0 (bảng A, B) và §4: trường đã có API trỏ tới `/topics`, `/pipeline/summary`;
   `docs/claude/design-system.md` §2.1 thêm token `--chart-dot` / `--chart-dot-faint` (2 màu chấm mockup landing đang
   dùng mà §2 chưa có) — mockup nên gọi đúng tên token này.
4. **Tầng reach (ADR-0012)** chưa có trên mockup nào: `UI-0012-reach-tiers`, `UI-0012-raw-views-reference`,
   `UI-0012-not-tiered` là ràng buộc cho lần thiết kế Analytics / Topics tới; mốc so sánh mô tả là "the channel's recent
   level (median of up to 20 prior posts)" (hạn chế cửa sổ 20 bài: `docs/claude/data-model.md`).
5. **Còn mở (Thy chốt ở Việc 1b):** nhóm so sánh theo topic — "phần còn lại của kênh" hay "median kênh".
6. **Từ khoá c-TF-IDF còn lẫn stopword tiếng Việt** ("một", "điều", "tui", "tớ", "ko"…) — lỗi phương pháp, không phải
   chữ; Thy chọn sửa bằng ADR + PR riêng trước khi công khai trang (2026-10-08). Mockup đừng chép bộ từ khoá hiện tại.
