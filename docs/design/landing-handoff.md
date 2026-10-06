# Handoff: Landing Unthreaded (tầng B) — 2026-10-01

> Đọc khi: port landing từ mockup sang `src/dashboard/`. Đọc kèm `docs/claude/design-system.md` (v3.2 — §2.6 dải tối, §7 tầng B).
> Mockup: `src/dashboard/mockups/landing.dc.html` — **tham chiếu thiết kế viết bằng HTML**, không copy nguyên vào app. Dựng lại bằng Next.js 16 + Tailwind v4 + token trong `globals.css` theo pattern sẵn có của repo.
> Fidelity: **hi-fi**. Màu, cỡ chữ, khoảng cách, copy và tương tác là bản cuối. Copy tiếng Anh lấy **nguyên văn** từ mockup.

## 0. Nguồn sự thật — đọc trước mọi thứ

**Code + DB của repo là nguồn sự thật duy nhất về số liệu và methodology.** Mockup chỉ quyết định bố cục, màu, chữ, tương tác. Mọi con số trong mockup được gõ tay từ bản sao `threads.db` (fetched 2026-10-01 12:12 UTC) để minh hoạ — **không đọc, không copy số từ `landing.dc.html`**. Khi mockup và code lệch nhau, code đúng; ghi lệch vào PR, không sửa code cho khớp mockup.

Kiểm toán 2026-10-02 — mỗi trường trên UI thuộc 1 trong 3 loại:

**A. Có sẵn trong repo, đọc thẳng được**

| Trường UI | Nguồn |
|---|---|
| engagement % từng bài | `PostInsights.engagement_rate` (`src/api/models.py`) — `(likes+replies+reposts+quotes)/views×100`; trả 0.0 khi views = 0 → **phải lọc trước** (ADR-0011, `src/analysis/stats.py`) |
| median / IQR kênh, n = 144, 6 bị loại | `window_stats` + `DistributionStatsOut` (`src/main.py`) |
| 353 / 674 / 342 vai reply | `posts.reply_role` (ADR-0004) |
| cụm, `centroid_similarity` | `post_topic_labels.confidence`, API đổi tên thành `centroid_similarity` (`src/main.py:258`) |
| từ khoá c-TF-IDF, 3 bài gần tâm | `topics.keywords_json`, `topics.representative_ids_json` (`src/nlp/topic_profile.py`, `clustering_import.py`) — **chưa có trong `TopicOut`** |
| toạ độ bản đồ | `content_units.umap_x/y/z` |
| 9 cụm · nhiễu 36,1% · DBCV (validity_index) 0,317 | `cluster_runs.n_clusters/noise_ratio/dbcv` — DBCV ghi kèm tên hàm `validity_index` |
| ARI 0,22 / 0,78 / 1,00 | `cluster_runs.ari_vs_previous/ari_clustered_only`: run 2 so run trước = 0,22 (cả nhiễu) / 0,78 (chỉ bài có cụm); run 3 (chạy lại cùng tham số) = 1,00 |
| CMI | `content_units.language_mix_score` (Code-Mixing Index, `src/nlp/language.py`) |
| stack, lịch job, model | `docs/claude/architecture.md`, ADR-0013, `topics.py:CLUSTER_LABELING_MODEL` |

**B. Tính từ dữ liệu thật trong Claude Design, repo CHƯA có hàm/endpoint** — Claude Code phải tự tính bằng code của repo, không chép số:

| Trường UI | Cách mockup tính | Phải làm trong repo |
|---|---|---|
| median/IQR/n từng cụm | quantile nội suy tuyến tính trên `er` | endpoint topic stats (status.md Next) |
| Cliff's δ, p, p Holm từng cụm | mỗi cụm vs phần còn lại của kênh (gồm nhiễu); **p bằng xấp xỉ chuẩn, không hiệu chỉnh ties**; Holm trên 9 test | `compare_groups()` (`src/analysis/significance.py`) + thêm Holm; chốt nhóm so sánh (vs rest hay vs median kênh) trước khi code |
| hàng nhiễu (median 2,05%) | như trên | cùng endpoint |
| "higher than 128 of 144" | đếm bài có rate nhỏ hơn | tính trong API/landing |
| CMI chia 3 nhóm, δ, p | tertile tự chọn, xấp xỉ chuẩn | **RQ-04 chưa làm** — chỉ hiện trạng thái research, không hiện số |

**C. Câu chữ diễn giải** (không phải số): Q1–Q3 ở Problem, mô tả node trong sơ đồ, câu trả lời 1 dòng. Câu trả lời 1 dòng phải **sinh từ kết quả tính** (VD "None clearly" chỉ đúng khi mọi p Holm ≥ 0,05) — không hardcode câu kết luận.

Đã sửa trong mockup 2026-10-02: số test 321 (sai — status.md ghi 397; giờ bỏ số), "API computes group comparisons" (sai — chưa có endpoint), mô tả gọi Claude API (`label_cluster_with_claude` — từ ADR-0018 chỉ gọi cho cụm cần đặt lại tên, không phải mọi cụm mỗi lần chạy; xem `docs/design/ui-contract-audit.md`).

## 1. Thay đổi so với landing hiện tại (`src/dashboard/src/app/page.tsx`)

| Component hiện có | Việc |
|---|---|
| `LandingNav.tsx` | Giữ, đổi link: Problem · Approach · Proof · How it works · About + nút "View live dashboard" |
| `LandingHero.tsx` | Làm lại: H1 tagline + panel bằng chứng (beeswarm, toggle Channel/Topic) |
| `LandingProblem.tsx` | Viết lại thành 3 câu hỏi Q1–Q3 (bỏ icon, bỏ vấn đề kỹ thuật) |
| `LandingSolution.tsx` | Thành "How it solves": 3 tầng nối nhau theo 1 bài thật |
| `LandingTechStack.tsx` | Thay bằng sơ đồ "How it works" trên dải tối |
| `LandingAuthor.tsx` | Đổi layout theo design-system §10 (ảnh 200×240, radius 16) + chip 9 cụm |
| mới | `LandingProof.tsx` (2 panel), `LandingCta.tsx`, footer |

Tên file mới phải thêm vào `planned_paths` trong `docs/decisions/invariants.toml` trước khi nhắc trong docs, nếu không `check --all` báo đường dẫn chết.

## 2. Layout chung

- Nền trang `--bg-page`. Nội dung `max-width 1200px`, padding ngang 32px. Section padding dọc 104px, ngăn bằng `border-top 1px --rule`.
- Navbar: pill trắng, viền hairline, sticky `top 16px`, căn giữa.
- Eyebrow: IBM Plex Mono 13px w500 `--amber-600`, dạng `01 · Problem`.
- H2 section: `clamp(32px, 3.6vw, 46px)` w800, `letter-spacing -0.035em`, `line-height 1.08`, `text-wrap: balance`.
- Panel bằng chứng: nền `--bg-card`, hairline, radius 20, padding `28px 32px 20px`. Thứ tự bắt buộc: **câu hỏi** (13px w600 amber) → **câu trả lời 1 dòng** (24px w700 −0.02em) → biểu đồ → hàng chân (ghi chú + nút "Method and limits") → khối phương pháp mở ra (`--bg-sunken`, radius 12, công thức mono 12.5px).
- Nút chính: pill `--amber-600`, chữ trắng 15px w600, cao 48. Nút phụ: pill trắng, hairline.

## 3. Từng section

### 3.1 Hero
- Logo động `brand/unthreaded-lockup-animated.svg` cao 64 (chỉ dùng ở đây). `prefers-reduced-motion` → `unthreaded-lockup.svg`.
- H1 `clamp(44px, 6.4vw, 76px)` w800 −0.04em lh 1.
- Panel: câu hỏi `Is "8 kinh nghiệm sau 8 năm ở Pháp" a strong post?` (post `17939285085325700`).
- Beeswarm cao 250: trục x 0–5.6%, vạch 0…5%. Mỗi chấm 8px `--text-muted` = 1 root post đo được. Xếp chấm: lần lượt theo giá trị tăng dần, thử y = tâm, tâm±9, tâm±18… lấy vị trí đầu tiên không chạm chấm đã đặt (khoảng cách ≥ 9px). Band IQR nền `--bg-surface` radius 6; vạch median 2px `--text-primary` + nhãn mono `median 1.99%`; nhãn `IQR 1.42–2.54%` đặt **bên phải** vạch median.
- Bài hero: chấm 16px `--amber-600`, viền trắng 3px + vòng amber 1px; callout `This post · 3.22%` + `higher than 128 of 144`.
- Toggle (pill trong `--bg-surface`): **Channel · n = 144** / **Topic · n = 13**. Topic: chấm khác mờ 50%, median 2.45%, IQR 2.10–2.88%, câu trả lời đổi sang "Above its topic's median too, but 13 posts is a small sample."
- Chân: `6 excluded: no views recorded` (ADR-0011).

### 3.2 Problem
Lưới 2 cột (`minmax(min(100%,420px),1fr)`, gap 56). Trái: eyebrow, H2, đoạn giới thiệu kênh. **Không sticky** (gãy khi xuống 1 cột). Phải: Q1–Q3, mỗi câu: nhãn mono `Q1`, câu hỏi 26px w700, lưới `112px | 1fr` hai dòng "Threads shows" (muted) / "Missing" (primary).

### 3.3 How it solves
- Thanh input nền `--dark-bg`, radius 16: trích dòng đầu bài hero + `root + its continuations, rebuilt from the reply graph`.
- Ba đường dọc 2px `--amber-on-dark` nối xuống tầng 01, 02; tầng 03 nối bằng `--rule` (chưa chạy).
- Lưới `1fr 64px 1fr 64px 1fr` (cuộn ngang trong container khi < 980px). Thẻ 01 Measure, 02 Group: `border-top 3px #F59E0B`, chip `live`. Thẻ 03 Search: nền `--bg-sunken`, viền dashed, chip `next`.
- Mỗi thẻ có ô "This post": Measure = strip mini 144 chấm + 3.22% · above 128 of 144 · median 1.99%; Group = mini map, cụm 7 amber + `Studying and Living in France · nearest post to the centre (0.888)`; Search = `document · full_text · topic_7 / indexed with 674 author answers` (id bền `topic_N`, ADR-0018 — mockup còn ghi `cluster_N`, xem audit).
- Cột nối: `←` amber "topic becomes the comparison group"; `→` muted "text and topic become documents".

### 3.4 Product proof
**Panel 1 — Which topics get more engagement than the channel?** Bảng `minmax(150px,240px) 44px 1fr 64px 52px 60px`: tên cụm, n, strip (chấm 6px, IQR band, vạch median 3px), median, Cliff's δ, p Holm. Đường dashed `--text-primary` = median kênh 1.99%. Cụm dẫn đầu chữ amber w600, IQR `--amber-soft`. Cụm n < 10 mờ 50% (hover/focus bỏ mờ). Hàng cuối "Unclustered (HDBSCAN noise)" n 52, chấm rỗng, `not tested`. Hover/focus hàng → ghi chú đổi thành mô tả hàng đó.

**Panel 2 — Do the topics describe real structure in the text?**
- Bản đồ UMAP (dim 1–2 của 3), tỉ lệ 4:3, nền `--bg-sunken`: chấm xám 7px, nhiễu = vòng rỗng, cụm đang chọn amber 10px. Legend luôn hiện.
- Danh sách 9 cụm (bar ngang theo n) là bộ chọn chính (design-system §9). Hồ sơ cụm: tên, id · n · median; từ khoá c-TF-IDF (chip `--amber-soft`); 3 bài gần tâm + `centroid_similarity` 3 chữ số.
- Ổn định (ARI): rerun cùng seed 1.00 · so lần trước, chỉ bài có cụm 0.78 · tính cả nhiễu 0.22 · 10 seed = ô dashed `—` (research, RQ-01).
- CMI vs engagement: chip `research · RQ-04`. **Không port số trong mockup** — hiển thị trạng thái research cho tới khi RQ-04 chạy `compare_groups()` + Holm.

### 3.5 How it works (dải tối, design-system §2.6)
- Canvas sơ đồ 1136×500 (cuộn ngang trong container). Node radius 12; tọa độ, nhãn, stack từng node lấy từ `NODES` trong mockup.
- Hàng trên: Threads Graph API → Collect (`every 4h · Task Scheduler`) → SQLite → API → Dashboard · Landing. Khung dashed `daily 12:30 · WSL2` (ADR-0017; mockup còn ghi giờ cũ — xem audit): Embed → Cluster → Name ↔ Claude API; Name → SQLite (`topics, labels`). Knowledge base (dashed, next), Classifier RQ-08 (dotted, research).
- Bấm node: viền + cạnh liên quan đổi `--amber-on-dark`, panel dưới hiện tên, chip trạng thái, mô tả, bảng stack mono. Mặc định chọn Cluster. Legend live/next/research bằng nét liền/đứt/chấm.
- Dòng chất lượng: `ruff · mypy strict · pytest 321 tests · 7 pre-commit gates` — lấy số test từ lần chạy thật, đừng hardcode.

### 3.6 About the channel
Lưới `200px | 1fr`, gap 48. Ảnh `photo_author` 200×240 radius 16 `object-position 50% 30%`. Bio **vẫn là nháp chờ Thy duyệt** (status.md). Chip 9 cụm kèm n.

### 3.7 CTA + footer
Khối `--dark-bg` radius 20, padding 80/32, mark 52px, H2 52px. Nút chính `--amber-on-dark` chữ `#111827`; 2 nút viền trắng 28%. Link dashboard/methodology/repo **chưa có URL thật** — giữ `#` tới khi deploy. Footer: lockup + tagline; câu miễn trừ Meta (ADR-0009) + `snapshot YYYY-MM-DD`.

## 4. Dữ liệu — không hardcode số

| Cần | Nguồn |
|---|---|
| Phân phối engagement, bài hero, rank | `GET /content-units` (`metrics.engagement_rate`), lọc views = 0 trước |
| Cụm, n, centroid_similarity, umap | `GET /content-units` (`topic`, `umap`) + `GET /topics` |
| Median/IQR/δ/Holm theo cụm | **mới**: endpoint topic stats (status.md Next, Bước 3–4) |
| Từ khoá, 3 bài đại diện | **mới**: mở rộng `TopicOut` với `keywords_json`, `representative_ids_json` |
| ARI, DBCV, nhiễu | **mới**: `/research/runs` (roadmap E) từ `cluster_runs` |
| CMI | research — chờ RQ-04 |

Landing là server component: fetch lúc build/request; lỗi API → empty state rõ ràng (design-system §9), không hiện khung trục rỗng.

## 5. Tương tác & a11y
- Transition 150ms ease-out, chỉ `transform`/`opacity`. Không count-up ở landing.
- Focus ring 2px `--amber-600` (trên dải tối dùng `--amber-on-dark`). Hàng bảng, cụm, node đều tới được bằng Tab; tooltip/ghi chú đổi cả khi focus.
- Vùng chạm ≥ 44px (nút "Method and limits" cao 44).
- Test 375/768/1024/1440: các khối rộng (chuỗi 3 tầng, bảng proof, sơ đồ) cuộn ngang **trong container**, trang không cuộn ngang.

## 6. Dọn repo cùng lúc

```bash
git rm src/dashboard/mockups/threads-dashboard.dc.html src/dashboard/mockups/threads-dashboard.html
```

## 7. Gọi Claude Code trong VS Code

1. `git status` (Claude Design không ghi trực tiếp vào repo; đảm bảo không có thay đổi lạ). Tạo nhánh trong worktree riêng: `/git-flow start feat/landing-v2` (ADR-0019 — thư mục chính luôn ở `main`).
2. Mở Claude Code trong VS Code, dán prompt:

```
/prime landing tầng B
Port landing theo docs/design/landing-handoff.md — đọc §0 trước. Tham chiếu hình: src/dashboard/mockups/landing.dc.html
(mở bằng browser để xem tương tác). Nguồn sự thật design: docs/claude/design-system.md v3.2.
Nguồn sự thật số liệu: code + DB của repo. KHÔNG đọc số từ mockup. Trường loại B ở §0 → viết hàm/endpoint
trong src/ (tái dùng compare_groups, window_stats), có test, rồi mới dựng UI. Trường chưa có → trạng thái
next/research, không điền số giả.
Thứ tự: (1) token §2.6 vào globals.css; (2) LandingHero; (3) LandingProblem; (4) How it solves;
(5) LandingProof panel 1 với /content-units, panel 2 phần đã có API, phần chưa có → trạng thái research;
(6) sơ đồ How it works; (7) Author, CTA, footer. Copy tiếng Anh giữ nguyên văn từ mockup.
Không hardcode số liệu; views = 0 loại khỏi phân phối và ghi số bị loại (ADR-0011).
Sau mỗi section: npm run lint && npm run typecheck, chụp npm run screenshots, so với mockup.
Cuối cùng đề xuất /checkpoint, chờ tôi duyệt.
```

3. So kết quả với mockup ở cùng độ rộng 1440 và 768. Khác biệt → sửa code, không sửa mockup (dev-rules: pipeline tuyến tính).
