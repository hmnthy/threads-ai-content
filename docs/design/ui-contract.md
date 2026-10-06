# Hợp đồng UI — Unthreaded

> Cập nhật tới: ADR-0020 · 2026-10-06
>
> **Đọc khi:** trước mọi phiên thiết kế (Claude Design) và trước khi port mockup sang code (Claude Code).
> **Vì sao có file này:** ADR-0020. Chiều thay đổi chỉ có một: **ADR → hợp đồng này → mockup → code.** Mockup cần thứ
> mà ADR chưa cho phép thì Claude Design viết brief gửi sang, không tự quyết.
> **Không neo số liệu.** Mỗi dòng neo một khái niệm, một trường, một trạng thái hoặc một ràng buộc trình bày — không
> neo con số thay đổi theo cron. Tham số cố định của code (VD "tối đa 15 bài") thì ghi kèm `file:line`.

## Đọc bảng thế nào

| Cột | Nghĩa | Ai viết |
|---|---|---|
| id | `UI-<ADR>-<slug>`; quyết định trước ADR-0001 dùng `UI-L<ngày>-<slug>`. Không tái dùng id | Claude Code |
| ADR | ADR nguồn (hoặc mục legacy-log / design-system) | Claude Code |
| A — Khái niệm / trường | Bảng.cột hoặc trường API thật. "(DB, chưa có API)" = có trong DB nhưng `src/main.py` chưa trả | Claude Code |
| B — Ràng buộc kỹ thuật | 1 câu khẳng định, kiểm được trong code, kèm `file:line` | Claude Code |
| C — Trang | `landing` · `overview` · `analytics` · `topics` · `all` | Claude Code |
| D — Kiểm bằng | Mã luật trong `docs/decisions/invariants.toml` · `test:` tên test · `manual` | Claude Code |
| E — Trình bày | Quy tắc trình bày 1 câu — **bản nháp**, Claude Design duyệt / đề xuất sửa qua brief | Claude Code nháp, Claude Design chốt |

**Máy giữ hợp đồng này đúng** (`scripts/consistency/check.py`, chặn commit): mốc "Cập nhật tới" không được tụt sau ADR
mới nhất; mọi ADR có ít nhất 1 dòng (ADR không chạm UI ghi "không có hệ quả UI"); id không trùng; mã luật và tên test
ở cột D phải có thật; ADR từ 0020 phải có mục `### Hệ quả UI`. Đường dẫn trong backtick ở cột B được kiểm như mọi tài
liệu (đường dẫn chết bị chặn).

**Thêm ADR mới:** ADR ghi mục "Hệ quả UI" → thêm/sửa/bỏ dòng ở đây trong **cùng commit** → nâng mốc "Cập nhật tới".

## ADR-0001 — phạm vi sản phẩm

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0001-dropped-scope | 0001 | — | Sản phẩm có đúng 3 lớp — thống kê, NLP, knowledge base (`src/dashboard/src/components/LandingSolution.tsx:3-22`); API chỉ có endpoint GET, không có thao tác ghi hay đăng bài (`src/main.py:236-604`) | all | `ADR0001-generation`, `ADR0001-content-idea` | Không nút, tab hay khối nào gợi ý tạo bài, tạo ảnh slide hay đăng bài; mọi tương tác chỉ là xem, lọc, chọn |
| UI-0001-status-labels | 0001 | Pill trạng thái: `StackItem.status`, `LAYERS[].status`; thẻ chỉ số `IndexCard.status` | Pill lộ trình trên landing có kiểu `"live" \| "next" \| "research"` (`src/dashboard/src/components/LandingTechStack.tsx:4`, `src/dashboard/src/components/LandingSolution.tsx:7`); thẻ chỉ số ở Overview dùng tập riêng `"live" \| "deferred"` (`src/dashboard/src/components/MetricArchitectureGrid.tsx:4`) | landing, overview | `ADR0001-coming-soon` | Pill lộ trình chỉ dùng live / next / research; pill độ sẵn sàng của chỉ số chỉ dùng live / deferred; không thêm nhãn khác (xem Câu hỏi mở 2) |
| UI-0001-kb-next | 0001 | Lớp Knowledge base (`LAYERS[2]`, thẻ "Knowledge base retrieval") | Knowledge base mang trạng thái `next` (`src/dashboard/src/components/LandingSolution.tsx:19`, `src/dashboard/src/components/LandingTechStack.tsx:26`) và API chưa có endpoint hỏi đáp/truy xuất (`src/main.py:236-604`) | landing | manual | Knowledge base và hỏi đáp chỉ xuất hiện như lớp `next`; không ô nhập câu hỏi hay demo trả lời trước cổng Phase F |
| UI-0001-classifier-research | 0001 | Bộ phân loại 6 nhãn (RQ-08) | Bộ phân loại có giám sát chỉ là câu hỏi nghiên cứu, trạng thái `research` (`src/dashboard/src/components/LandingTechStack.tsx:25`); Topic Explorer chỉ lấy topic `method === "cluster"` (`src/dashboard/src/components/TopicExplorer.tsx:87`) | landing, topics | `ADR0001-svm-in-pipeline` | Bộ phân loại chỉ hiện như mục research tách khỏi pipeline, không vẽ thành bước nối với HDBSCAN |

## ADR-0003, ADR-0008 — tài liệu, sổ luật

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0003-no-ui-impact | 0003 | — | không có hệ quả UI | — | — | — |
| UI-0008-forbid-copy | 0008 | Chữ hiển thị trong code dashboard | Luật `[[forbid]]` quét mọi file đã track trong phạm vi `paths` của nó — gồm code dashboard — và chặn commit khi chữ vi phạm (`scripts/consistency/check.py`, `docs/decisions/invariants.toml`) | all | test: `test_forbid_reports_file_line_and_rule` | Chữ trong mockup viết như thể đã nằm trong code: khi port, mọi vi phạm sẽ chặn commit (mockup được quét ở mức cảnh báo — UI-0020-mockup-scan) |

## ADR-0004 — vai trò reply, văn bản sạch, chất lượng cụm

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0004-full-text-scope | 0004 | `content_units.full_text`, `ContentUnitOut.full_text`, `ContentUnitOut.continuation_count`, `posts.reply_role` | `full_text` chỉ gồm root, các reply vai `self_continuation` theo thứ tự đọc và `text_attachment`; reply `author_answer`/`outbound` không bao giờ được gộp (`src/processing/thread_reconstruction.py:89-105`, `:130-138`) | topics, landing | test: `test_answers_to_followers_stay_out_of_full_text` | Đơn vị phân tích mô tả là "post + the author's follow-up parts", không bao giờ "post + replies/comments" |
| UI-0004-centroid-similarity | 0004 | `post_topic_labels.confidence` → `TopicLabel.centroid_similarity` | API trả cosine giữa embedding bài và tâm cụm dưới tên `centroid_similarity` (có thể null) — không phải xác suất thuộc cụm (`src/main.py:103-108`, `:264-271`, `src/pipeline/clustering_import.py:405-413`) | topics | test: `test_content_units_endpoint_returns_metrics_and_topic` | Ghi "similarity to cluster centre" dạng thập phân; không dùng chữ "confidence", không dùng % |
| UI-0004-representatives | 0004 | `topics.representative_ids_json` (DB, chưa có API) | Mỗi cụm lưu `REPRESENTATIVES_PER_TOPIC` = 3 bài gần tâm nhất theo cosine trên embedding đã lưu (`src/nlp/topic_profile.py:39`, `:147-158`) | topics, landing | test: `test_representatives_pick_posts_closest_to_centroid` | Khối "3 posts nearest the centre" là bài đại diện để đọc, kèm `centroid_similarity`; không mô tả là đầu vào của Claude (UI-0016-label-input) |
| UI-0004-noise-basis | 0004 | `cluster_runs.noise_ratio`, `cluster_runs.n_units`, nhóm "Unclustered" | `noise_ratio` = số bài nhãn -1 chia `n_units` (số unit có `full_text` không rỗng đã export đi gom cụm) (`src/pipeline/clustering_import.py:270-275`, `src/pipeline/clustering_export.py:71`) | topics, landing | test: `test_run_import_stores_embeddings_profiles_and_run_metrics` | Tỉ lệ nhiễu luôn ghi mẫu số "of N embedded posts"; nhóm nhiễu hiện riêng "Unclustered (HDBSCAN noise)", không xếp như một topic |
| UI-0004-dbcv-named | 0004 | `cluster_runs.dbcv` (= `hdbscan.validity.validity_index`), `cluster_runs.dbcv_relative` (= `relative_validity_`) — chưa có API | Cột `dbcv` lưu `validity_index` (DBCV đầy đủ, null khi < 2 cụm), `dbcv_relative` lưu `relative_validity_` (xấp xỉ); hai số khác thang (`src/db/schema.py:132-135`, `src/pipeline/cluster_wsl.py:109-118`) | topics, landing | `ADR0004-dbcv-unnamed` | Số DBCV luôn đi cùng tên hàm `validity_index` ngay cạnh; không đặt `relative_validity_` cạnh nó; null → "not computed (fewer than 2 clusters)" |
| UI-0004-ari-two-ways | 0004 | `cluster_runs.ari_vs_previous`, `cluster_runs.ari_clustered_only`, `cluster_runs.transitions_json` (DB, chưa có API) | Mỗi lần gom cụm lưu 2 ARI so lần trước — coi nhiễu là 1 nhóm, và chỉ trên bài có cụm ở cả hai lần; < 2 bài để so thì null (`src/pipeline/clustering_import.py:167-192`, `src/db/schema.py:136-140`) | topics, landing | test: `test_compare_with_previous_separates_noise_moves_from_regrouping` | Nhãn mỗi ARI ghi rõ cách tính; `ari_clustered_only` không đứng một mình như "độ ổn định"; không có ARI nào mà code không tạo ra |

## ADR-0009, ADR-0010 — tên sản phẩm, CSDL

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0009-display-name | 0009 | `metadata.title`, `FastAPI(title=…)`, logo navbar | Tên hiển thị là "Unthreaded" ở title trang (`src/dashboard/src/app/layout.tsx:19`), logo hai navbar (`src/dashboard/src/components/Nav.tsx:28`, `src/dashboard/src/components/LandingNav.tsx:15`) và title API (`src/main.py:65`); slug repo chỉ dùng cho định danh kỹ thuật | all | `ADR0009-old-name`, `ADR0009-old-name-variants` | Mọi chỗ hiện tên sản phẩm ghi "Unthreaded"; không hiện slug repo trên UI |
| UI-0009-tagline | 0009 | Tagline | Tagline "The algorithm, read back to you." có ở topbar app và H1 landing (`src/dashboard/src/components/Nav.tsx:31`, `src/dashboard/src/components/LandingHero.tsx:14`) | all | manual | Tagline giữ nguyên văn, đi cùng tên Unthreaded ở topbar và hero |
| UI-0009-meta-disclaimer | 0009 | Footer landing | Footer landing chứa nguyên văn câu miễn trừ Meta (`src/dashboard/src/app/page.tsx:26-27`), test chặn khi câu này mất (`tests/test_branding.py:15-29`) | landing | test: `test_meta_disclaimer_present` | Câu miễn trừ giữ nguyên văn ở footer mọi bản landing; chữ "Threads" không đứng đầu tên sản phẩm hay logo |
| UI-0009-screenshots | 0009 | Ảnh README của 4 trang | Ảnh README của landing, overview, analytics, topics bị đánh dấu lỗi thời khi navbar/tên đổi, chụp lại bằng `npm run screenshots` (`docs/decisions/invariants.toml`, `src/dashboard/package.json`) | all | `ADR0009-landing-screenshot`, `ADR0009-overview-screenshot`, `ADR0009-analytics-screenshot`, `ADR0009-topics-screenshot` | Handoff của mockup nào đổi navbar hay tên ghi rõ trang nào cần chụp lại ảnh sau khi port |
| UI-0010-sqlite-only | 0010 | Thẻ Database (`STACK`, dòng "Database") | Thẻ Database của tech stack ghi `SQLite`, trạng thái `live`; knowledge base dự kiến nằm trong cùng file SQLite (`src/dashboard/src/components/LandingTechStack.tsx:19`, `:26`) | landing | `KB-no-separate-vectorstore` | Tầng dữ liệu chỉ nêu SQLite (1 file, 1 tiến trình ghi) như lựa chọn có chủ đích; không nhắc CSDL nào khác như hướng tương lai |

## ADR-0011 — bài views = 0 là dữ liệu thiếu

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0011-excluded | 0011 | `AnalyticsOverviewOut.excluded_no_views`, `WindowAnalyticsOut.excluded_no_views` (từ `split_measurable`) | `split_measurable()` chỉ giữ bài có snapshot mới nhất `views > 0` và trả số bị loại; `/analytics/overview` và `/analytics/window` trả số này là `excluded_no_views` (`src/analysis/stats.py:72-86`, `src/main.py:387`, `:473`) | landing, overview, analytics, topics | test: `test_analytics_overview_excludes_zero_view_posts_and_reports_them` | Mọi khối hiện phân phối rate ghi đúng 1 câu "N excluded: no views recorded" khi N > 0 (code hiện có 4 cách viết khác nhau — thống nhất khi port) |
| UI-0011-count-basis | 0011 | `AnalyticsOverviewOut.post_count`, `WindowAnalyticsOut.content_unit_count` | `post_count` của `/analytics/overview` đếm sau khi loại `views == 0`, còn `content_unit_count` của `/analytics/window` đếm cả bài bị loại (`src/main.py:186-189`, `:225-228`, `:410`, `:479`) | overview, analytics | test: `test_analytics_overview_excludes_zero_view_posts_and_reports_them` | Nhãn số đếm nói rõ cơ sở — "posts measured" hay "posts in window"; không đặt hai số cạnh nhau như cùng đại lượng |
| UI-0011-no-zero-rate | 0011 | `ContentUnitOut.metrics.{engagement_rate, share_rate, conversation_rate}`, `TopPostEntry.metrics` | Rate từng bài trả `0.0` khi `views == 0` (guard chia 0) và `/content-units` không lọc các bài này (`src/api/models.py:100-101`, `src/analysis/share_rate.py:24-25`, `src/main.py:253-262`) | topics, analytics | manual | Bài views = 0 hiện rate "—" kèm "no views recorded", không bao giờ "0%"; client không tự đưa bài đó vào phân phối |
| UI-0011-two-exclusions | 0011 | `excluded_no_views` (API); unit không có chữ (`content_units.full_text` rỗng) | Loại vì `views == 0` (theo snapshot) và loại vì `full_text` rỗng (theo văn bản) là hai điều kiện độc lập trong code, không ràng buộc nào buộc hai tập trùng (`src/analysis/stats.py:83`, `src/pipeline/clustering_export.py:71-72`) | topics, landing | manual | Hai dòng loại riêng, mỗi dòng có mẫu số riêng: "N have no text to embed" và "N excluded from rates: no views recorded" |

## ADR-0012 — share rate, tầng reach

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0012-share-rate-name | 0012 | `ContentUnitMetrics.share_rate`, `AnalyticsOverviewOut.top_by_share_rate`, `WindowAnalyticsOut.share_rate` | (reposts + quotes) / views × 100 mang tên `share_rate`; tên cũ không còn trong code hay API (`src/analysis/share_rate.py:15-25`, `src/main.py:92-100`) | landing, overview, analytics | `ADR0012-old-share-name`, `ADR0012-old-label-wording` | Nhãn "Share rate" (bảng top: "Top by share rate"); không dùng tên cũ hay nhãn cũ ở bất kỳ đâu, kể cả mockup (2 luật ở cột D) |
| UI-0012-reach-tiers | 0012 | `ReachTiersOut.posts[].status` (`top_20`, `above_median`, `below_median`), `p50_ratio`, `p80_ratio`, `n_tiered` | Tầng xếp theo reach tương đối = views ÷ median views của tối đa 20 bài gốc đo được đăng ngay trước; ngưỡng P50 / P80 tính trên bài đã chín và có mốc, biên ≥ là đạt (`src/analysis/reach.py:102-125`, `:156-176`, `src/main.py:573-604`) | analytics, topics | test: `test_assign_reach_tiers_statuses_follow_priority_and_percentiles` | Hai nhãn tự giải thích "Top 20% reach" và "Above median reach"; dưới median không gắn nhãn; định nghĩa đi kèm là bội số so với mức bình thường của kênh lúc đăng ("≥ N× the channel's usual views at the time"), N đọc từ `p80_ratio` / `p50_ratio` |
| UI-0012-raw-views-reference | 0012 | `ReachTiersOut.posts[].views`, `p50_views`, `p80_views`; `posts[].baseline_views` | Views thô và views ở P50 / P80 của cùng nhóm bài chỉ là tham chiếu, không quyết định tầng; `baseline_views` là mốc so sánh (median views các bài đăng ngay trước, mẫu số của reach tương đối), không phải views thô, và chỉ có với bài đã xếp tầng (`src/analysis/reach.py:162`, `src/main.py:489-527`, `:598-599`) | analytics, topics | test: `test_assign_reach_tiers_reports_raw_views_reference_on_same_pool` | Views thô hiện ở vị trí phụ cạnh tầng; không sắp hay tô màu bài theo views thô khi đang nói về tầng |
| UI-0012-not-tiered | 0012 | `posts[].status` = `still_growing` / `no_baseline` / `maturity_unknown`; `maturity.days`, `maturity.n_curves`, `insufficient_data` | Bài trẻ hơn mốc chín, bài chưa có đủ 10 bài trước, hoặc khi chưa đo được mốc chín thì không được xếp tầng, API trả `relative_reach` và `baseline_views` = null; mốc chín = P90 thời gian đạt 90% views mới nhất (tuổi bài tính tại snapshot mới nhất), tính lại mỗi lần (`src/analysis/reach.py:84-99`, `:164-170`) | analytics, topics | test: `test_assign_reach_tiers_maturity_unknown_tiers_nothing` | "Still growing" là trạng thái trung tính, không phải tầng thấp; ghi chú phương pháp nêu mốc chín kèm số đường cong ("based on N posts"); cờ `insufficient_data` theo quy tắc mẫu nhỏ chung |

## ADR-0013, ADR-0014, ADR-0015 — cron, cổng kiểm, review

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0013-no-ui-impact | 0013 | — | không có hệ quả UI | — | — | — |
| UI-0014-no-ui-impact | 0014 | — | không có hệ quả UI | — | — | — |
| UI-0015-no-ui-impact | 0015 | — | không có hệ quả UI | — | — | — |

## ADR-0016 — đặt tên cụm

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0016-label-input | 0016 | Mẫu bài gửi Claude để đặt tên (`sample_texts` của `label_cluster_with_claude`, không phải trường API) | Prompt đặt tên nhận tối đa 15 bài của cụm — xếp theo cosine giảm dần tới tâm khi có embedding (không có thì theo thứ tự thành viên) — chỉ chứa văn bản bài, không có từ khoá c-TF-IDF (`src/nlp/topics.py:124`, `src/pipeline/clustering_import.py:255-260`, `src/nlp/topic_profile.py:156-158`) | landing, topics | manual | Node "Name" ghi "up to 15 posts nearest the centre", không ghi keywords là đầu vào của Claude; tách khỏi khối bài đại diện (UI-0004-representatives) |
| UI-0016-no-old-model | 0016 | `CLUSTER_LABELING_MODEL`; `topics.label_model` (DB, chưa có API) | Model đặt tên hiện hành là `claude-sonnet-5-5`; sổ luật cấm nhắc model đặt tên cũ ngoài `docs/decisions/` (`src/nlp/topics.py:54`) | all | `ADR0016-opus-labeling` | Ghi nguồn tên là "named by Claude"; không hard-code tên model — khi cần hiện thì đọc `label_model` của từng topic (khi API có) |
| UI-0016-no-caching-claim | 0016 | — | Lời gọi đặt tên không gửi `cache_control` (`src/nlp/topics.py:141-146`) | landing | `ADR0016-prompt-caching` | Tech stack và sơ đồ pipeline không nhắc "prompt caching" cho bước đặt tên <!-- consistency: allow ADR0016-prompt-caching --> |

## ADR-0017 — lịch job, khoảng hở snapshot

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0017-nlp-schedule | 0017 | Lịch task `ThreadsAI_NLPClusterJob_Daily` | Job NLP đặt chạy hằng ngày 12:30 giờ máy, StartWhenAvailable nên lượt lỡ chạy bù muộn hơn (`scripts/configure_jobs.ps1:22`, `:32`, `:35-37`) | landing | `ADR0017-nlp-3am` | Sơ đồ pipeline ghi "daily 12:30 (machine time)", không giờ đêm/"nightly"; mốc lần chạy thật lấy từ `run_at`, không suy từ giờ lịch <!-- consistency: allow ADR0017-nlp-3am --> |
| UI-0017-run-time | 0017 | `cluster_runs.run_at` (DB, chưa có API) | `run_at` là thời điểm UTC ở bước import của mỗi lần gom cụm: mọi bài được gán lại topic, hồ sơ cụm cập nhật, tên chỉ đổi ở cụm cần đặt lại tên (`src/pipeline/clustering_import.py:326`, `:416-418`) | topics, landing | manual | Có mốc "clustered <ngày giờ>" từ `run_at` mới nhất, ghi rõ múi giờ (Câu hỏi mở 4); số bài mỗi topic đọc là "tính tới lần chạy đó" |
| UI-0017-night-gaps | 0017 | `insights_snapshots.fetched_at` (DB, chưa có API) | Snapshot lịch 4h nhưng chỉ chạy khi máy thức (Modern Standby đóng băng tiến trình); `snapshot_coverage` coi khoảng > 5h giữa 2 lượt là lỡ ít nhất 1 lượt (`scripts/configure_jobs.ps1:3-6`, `scripts/snapshot_coverage.py:41`) | overview, analytics | manual | Biểu đồ dựng từ snapshot không nối đường qua khoảng > 5h và vẽ khoảng hở ra; biểu đồ daily views (`account_daily_views`) không thuộc ràng buộc này |
| UI-0017-velocity-deferred | 0017 | `window_velocity`; `ContentUnitMetrics` chưa có velocity/longevity | `window_velocity` từ chối chuỗi dưới 3 snapshot, và API chưa trả velocity/longevity (`src/analysis/velocity.py:58-59`, `src/main.py:92-100`) | overview | test: `test_window_velocity_raises_below_three_snapshots` | Ô velocity và longevity giữ trạng thái deferred kèm lý do bằng chữ (thiếu snapshot), không số, không biểu đồ giả, không ô trống |
| UI-0017-snapshot-freshness | 0017 | `ContentUnitOut.metrics`, `TopPostEntry.metrics`; `insights_snapshots.fetched_at` (DB, chưa có API) | Chỉ số mỗi bài trên API tính từ snapshot mới nhất của bài đó, và API không trả thời điểm snapshot ấy (`src/main.py:254-256`, `:327-331`) | overview, analytics | manual | Chỉ số bài ghi "as of latest snapshot" (thêm giờ cụ thể khi API trả `fetched_at`), không ngụ ý thời gian thực |

## ADR-0018 — danh tính topic bền

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0018-id-not-name | 0018 | `topics.id` (`topic_N`) = `TopicOut.id` = `ContentUnitOut.topic.topic_id` | Id topic dạng `topic_N`; số mới lớn hơn mọi số từng có (bảng `topics` lẫn lịch sử) nên id không bao giờ tái dùng, còn `label_en` có thể đổi khi id giữ nguyên (`src/pipeline/clustering_import.py:114-127`, `src/db/schema.py:592-602`) | all | `ADR0018-cluster-id-display`, test: `test_vanished_topic_id_is_never_reused_even_right_after_migration` | Khoá, link, trạng thái chọn dùng id `topic_N` (không bao giờ `cluster_N`); tên chỉ để hiển thị (Câu hỏi mở 3) |
| UI-0018-label-provenance | 0018 | `topics.labeled_at`, `topics.label_model`, `topics.label_prompt_version`; `topic_label_history.reason`, `topic_label_history.sources_json` (DB, chưa có API) | Mỗi lần Claude đặt tên ghi 1 dòng lịch sử, reason ∈ new / split / merged / drift / config_change, kèm model và phiên bản prompt; `retired` là dòng đóng có `labeled_at` = lúc xoá (`src/pipeline/clustering_import.py:351-363`, `src/db/schema.py:148-161`) | topics, landing | test: `test_core_keeps_name_fragment_is_new_and_history_records_everything` | Tên luôn kèm "named by Claude"; nếu Việc 1e chọn hiện lịch sử thì ghi ngày đặt tên + lý do (nhãn tiếng Anh); `labeled_at` của dòng retired không phải ngày đặt tên |
| UI-0018-retired | 0018 | `topic_label_history.reason = 'retired'` (DB, chưa có API) | Topic biến mất bị xoá khỏi bảng `topics` nên không bao giờ có trong `GET /topics`, chỉ còn dòng `retired` trong lịch sử (`src/pipeline/clustering_import.py:351-364`, `src/main.py:298`) | topics | test: `test_vanished_topic_id_is_never_reused_even_right_after_migration` | Danh sách và bản đồ không có trạng thái retired (mọi topic API trả về đều đang sống); retired chỉ hiện trong lịch sử; id lạ trong state/URL rơi về chưa chọn |
| UI-0018-names-change | 0018 | `TopicOut.label_en`, `TopicOut.description_en` | Cụm giữ id vẫn được đặt lại tên khi tên đang lưu sinh bằng model/`LABEL_PROMPT_VERSION` khác hiện hành, khi chưa có bản neo, hoặc khi trôi khỏi bản neo (`src/pipeline/clustering_import.py:114-124`, `src/nlp/topics.py:54`, `:58`) | landing, topics | test: `test_plan_keeps_names_unless_drifted_or_labeled_with_another_config` | Trang tĩnh không hard-code tên topic như sự thật bền; tên mẫu trong mockup lấy từ file xuất (brief Việc 4), chỉ để minh hoạ |
| UI-0018-label-length | 0018 | `TopicOut.label_en`, `TopicOut.description_en` (nullable) | Prompt v2 yêu cầu `label` Title Case tối đa 5 chữ nhưng code không kiểm/cắt, và `description_en` nullable (`src/nlp/topics.py:133`, `:149`, `src/main.py:123-128`) | topics, landing | test: `test_label_prompt_v2_rules_are_sent_and_versioned` | Layout không giả định tên ≤ 5 chữ (xuống dòng, hoặc cắt + tooltip đủ tên); có trạng thái riêng khi không có mô tả |
| UI-0018-run-events | 0018 | `cluster_runs.topic_events_json` (DB, chưa có API) | Mỗi lần chạy ghi sự kiện từng topic ∈ kept / kept_semantic / relabeled / new / split / merged / retired (`src/pipeline/clustering_import.py:132-143`, `src/db/schema.py:142-143`) | topics | test: `test_core_keeps_name_fragment_is_new_and_history_records_everything` | Nếu Topics hiện "thay đổi từ lần chạy trước" thì dùng đúng tập sự kiện này (nhãn tiếng Anh), không suy từ việc so tên |

## ADR-0019, ADR-0020 — quy trình git, hợp đồng UI

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-0019-no-ui-impact | 0019 | — | không có hệ quả UI | — | — | — |
| UI-0020-contract-gate | 0020 | `docs/design/ui-contract.md` | Commit bị chặn khi có ADR mới hơn mốc "Cập nhật tới", ADR chưa có dòng nào, id trùng, hoặc cột D trỏ tới luật/test không có; ADR từ 0020 phải có mục "Hệ quả UI" (`scripts/consistency/check.py`) | all | test: `test_ui_contract_flags_stale_mark_missing_adr_and_ui_impact` | Mỗi quyết định cấu trúc trong mockup/handoff ghi id `UI-…` mà nó tuân theo; thứ ADR chưa cho phép thì viết brief, không tự quyết |
| UI-0020-mockup-scan | 0020 | `src/dashboard/mockups/*.dc.html`, `docs/design/*.dc.html` | Luật `[[forbid]]` có `mockups = true` quét các mockup này; vi phạm ở đó là cảnh báo, không chặn commit (`scripts/consistency/check.py`, `docs/decisions/invariants.toml`) | all | test: `test_mockup_hits_are_warnings_from_opted_in_rules_only` | Cảnh báo mockup được ghi vào `docs/design/ui-contract-audit.md`; Claude Design sửa ở vòng thiết kế kế tiếp |

## Quyết định trước ADR-0001 còn hiệu lực (legacy-log, design-system)

| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
|---|---|---|---|---|---|---|
| UI-L20260903-landing-vs-app-routes | legacy 2026-09-03 | Route `/`, `/overview`, `/analytics`, `/topics` | `/` là landing dùng `LandingNav` riêng, không tab; `/overview`, `/analytics`, `/topics` nằm trong route group `(app)` và dùng chung `Nav` với 3 tab (`src/dashboard/src/app/page.tsx:12-22`, `src/dashboard/src/components/Nav.tsx:10-14`) | all | manual | Landing có navbar riêng, mọi CTA dẫn tới `/overview`; 3 trang app dùng chung topbar và tab pill; không trộn hình khối tầng A với tầng B |
| UI-L20260903-stack-real-status | legacy 2026-09-03 | `StackItem.status` | Mỗi thẻ tech stack khai báo trạng thái theo code thật; thẻ không `live` đổi sang nền `bg-bg-sunken` với chữ muted (`src/dashboard/src/components/LandingTechStack.tsx:12-27`, `:43-50`) | landing | manual | Nhãn trạng thái phản ánh code đang chạy, không phản ánh roadmap; thẻ chưa live phải nhìn rõ là chưa có |
| UI-L20260903-window-median | legacy 2026-09-03 | `WindowAnalytics.engagement/share_rate/conversation` (`DistributionStats`) | Engagement, share rate, conversation của cửa sổ là median / mean / IQR / n của tỉ lệ từng bài qua `window_stats`, không phải tỉ lệ gộp Σinteractions/Σviews (`src/analysis/stats.py:89-97`, `src/main.py:482-484`) | overview, analytics | test: `test_window_stats_is_not_a_pooled_ratio` | Số lớn là median từng bài, mean và n ở dòng phụ (chờ Việc 1d); mockup không tự tính tỉ lệ gộp |
| UI-L20260903-two-views | legacy 2026-09-03 | `WindowAnalytics.views` vs `TopPostEntry.metrics.popularity_index` | `WindowAnalytics.views` là tổng `account_daily_views` trong cửa sổ (gồm views từ reply); `popularity_index` là views từng bài — không cộng dồn hay so trực tiếp được (`src/main.py:213-220`, `:478`) | overview | test: `test_analytics_window_computes_median_stats_and_views_from_daily_series` | Ô Views của cửa sổ ghi là views cấp tài khoản theo ngày; danh sách bài ghi views từng bài; không trình bày như cùng đại lượng |
| UI-L20260903-brush-handrolled | legacy 2026-09-03 | Timeline Brush (`onWindowCommit` → `/analytics/window`) | Brush tự viết bằng pointer capture, 2 tay cầm `role="slider"` điều khiển được bằng phím mũi tên, cửa sổ tối thiểu `MIN_WINDOW_DAYS = 5`, gọi API sau `COMMIT_DEBOUNCE_MS = 300`, không thư viện kéo thả (`src/dashboard/src/components/TimelineBrush.tsx:17-18`, `:143-153`) | overview | manual | Mockup chỉ dùng thao tác brush hiện có (kéo 2 đầu, kéo giữa, preset, phím mũi tên); số KPI chỉ đổi khi thả tay |
| UI-L20260829-two-clocks | legacy 2026-08-29 | `AnalyticsOverview.timezones[].timezone` | API trả phân phối engagement theo giờ và thứ cho đúng hai múi `Europe/Paris` và `Asia/Ho_Chi_Minh` trên cùng một tập bài (`src/main.py:135-138`, `:390-407`); heatmap cho đổi giữa hai đồng hồ (`src/dashboard/src/components/PostingTimeHeatmap.tsx:17-20`) | analytics | test: `test_analytics_overview_ranks_top_posts_per_metric_and_breaks_down_by_timezone` | Mọi biểu đồ giờ/thứ ghi rõ đồng hồ đang xem và cho đổi Paris ↔ Việt Nam; giờ của bài ghi theo giờ Paris và nói rõ |
| UI-L20260830-english-ui | legacy 2026-08-30 | `TopicOut.label_en`, `TopicOut.description_en` | Prompt đặt tên cụm yêu cầu label và description bằng tiếng Anh (`src/nlp/topics.py:130-132`); API trả `label_en`/`description_en` (`src/main.py:123-128`); trang khai báo `lang="en"` (`src/dashboard/src/app/layout.tsx:26`) | all | manual | Mọi chữ của sản phẩm bằng tiếng Anh; tên/mô tả topic hiển thị nguyên văn, không dịch lại; chỉ nội dung bài gốc giữ ngôn ngữ của nó |
| UI-L20260830-six-indices | legacy 2026-08-30 | `ContentUnitMetrics`, `INDICES` | Kiến trúc chỉ số gồm 6 index tách riêng, `ContentUnitMetrics` không có trường điểm tổng hợp (`src/main.py:92-100`, `src/dashboard/src/components/MetricArchitectureGrid.tsx:11-43`) | overview, landing | manual | Không hiển thị một "score" gộp; mỗi index có thẻ riêng kèm công thức mono và trạng thái |
| UI-L20260830-insight-fields | legacy 2026-08-30 | `PostInsights` | `PostInsights` chỉ có `views`, `likes`, `replies`, `reposts`, `quotes` (`src/api/models.py:88-94`) — không có shares, reach hay impressions | all | `ADR0012-raw-views-as-reach` | Không đặt ô hay nhãn cho shares / impressions hay một "reach" lấy từ API; chữ "reach" chỉ dùng cho tầng reach tương đối (`UI-0012-reach-tiers`, ADR-0012), không gọi views thô là "reach" |
| UI-L20260830-engagement-formula | legacy 2026-08-30 | `PostInsights.engagement_rate` | `engagement_rate` = (likes + replies + reposts + quotes) / views × 100 (`src/api/models.py:97-102`) | overview, analytics, landing | test: `test_post_insights_engagement_rate_formula` | Công thức hiển thị dạng mono, đủ 4 thành phần ở tử số (kể cả quotes), mẫu số là views chứ không phải follower |
| UI-L20260830-precomputed | legacy 2026-08-30 | `ContentUnitOut.umap` | API chỉ đọc kết quả NLP đã ghi trong SQLite, không chạy embedding/gom cụm theo request, nên bài chưa qua lần chạy NLP có `umap = null` (`src/main.py:1-6`, `:273-275`) | topics | manual | Topics hiện riêng số bài chờ lần chạy NLP kế tiếp; không có nút chạy lại gom cụm trên UI |
| UI-L20260902-no-text-excluded | legacy 2026-09-02 | `content_units.full_text` rỗng | Content unit có `full_text` rỗng bị loại khỏi export gom cụm (`src/pipeline/clustering_export.py:71`); Topic Explorer đếm riêng nhóm này, tách khỏi nhóm đang chờ và Unclustered (`src/dashboard/src/components/TopicExplorer.tsx:72-76`) | topics | manual | Bài không có chữ (VD repost không caption) là một dòng loại riêng có lý do, không gộp vào Unclustered |
| UI-L20260829-mobile | legacy (commit đầu 2026-08-29) | — | Lưới dashboard và landing mặc định 1 cột, chia cột từ breakpoint `sm`/`lg`; heatmap giờ 12 cột trên màn hẹp, 24 cột từ `lg` (`src/dashboard/src/components/PostingTimeHeatmap.tsx:205`) | all | manual | Mỗi mockup có khung hẹp (~375px): card 1 cột, heatmap giờ gãy thành 2 hàng 12 ô, bảng/sơ đồ cuộn ngang trong container |
| UI-L20260829-single-channel | legacy (commit đầu 2026-08-29) | Pill tài khoản ở topbar | Dashboard chỉ đọc dữ liệu một tài khoản; pill tài khoản là chữ cố định, không có handler (`src/dashboard/src/components/Nav.tsx:37-44`) | overview, analytics, topics | manual | Không thiết kế bộ chọn kênh hay so sánh kênh khác; pill tài khoản chỉ để nhận diện, không gợi ý menu |
| UI-L20260930-topic-single-accent | design-system §13 2026-09-30 | Màu scatter UMAP | Scatter UMAP tô mọi điểm bằng `--text-muted`, chỉ topic đang chọn tô `--amber-600`, không có bảng màu theo cụm (`src/dashboard/src/components/TopicExplorer.tsx:13-16`, `:119-124`) | topics | manual | Topics chỉ có một màu nhấn amber cho topic đang chọn; chọn topic qua danh sách bar, không gán mỗi cụm một màu |

## Câu hỏi mở (chưa thành dòng — chờ Thy / Claude Design chốt)

1. **Ngưỡng mẫu nhỏ trên UI.** Code có đúng một ngưỡng: cờ `insufficient_data` khi n < `MIN_N_PER_BUCKET` = 5
   (`src/analysis/engagement.py:23`), dùng chung cho bucket giờ/thứ, phân phối cửa sổ và `compare_groups`. Landing
   mockup làm mờ cụm n < 10 — số 10 chưa có trong code, và `HDBSCAN_MIN_CLUSTER_SIZE` = 4 (`src/nlp/topics.py:45`) nên
   cụm 4–9 bài có thật. Chốt ở brief Việc 1 / 2.7; nếu là 10 thì cần hằng số mới có tên + lý do. Dù chốt số nào, UI
   đọc cờ từ backend, không so số ở client.
2. **Bộ nhãn trạng thái.** ADR-0001 không định nghĩa live / next / research (chỉ luật `ADR0001-coming-soon` nêu); code
   có thêm `deferred` cho thẻ chỉ số. Giữ hai tập riêng hay gộp `deferred` thành `next`?
3. **Hiện id topic cho người đọc?** Landing mockup hiện id trong hồ sơ cụm và chú thích. Minh bạch cho người đọc kỹ
   thuật, hay chỉ dùng id làm khoá ẩn — quyết định trình bày của Claude Design.
4. **Múi giờ của mốc "clustered".** `run_at` lưu UTC; lịch 12:30 là giờ máy (Paris). Hiện giờ Paris kèm nhãn, hay cả
   hai?
