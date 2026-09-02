# Sprint Plan v3 — Phase 1 (Data + NLP Foundation + MLOps + Dashboard + Generation)

> Cập nhật: 2026-09-02 — redesign v3. Thay đổi so với v2 (2026-08-30): (1) snapshot job & data archive đẩy lên **Ngày 0** vì đây là dữ liệu không hồi cứu được, (2) chèn **MLOps track** (CI/CD, Docker, MLflow, deploy) song song thay vì bỏ trống — khớp trực tiếp mục tiêu ML Engineer, (3) thêm **Ngày 2 gán nhãn 140 post** vì `data/labels/topic_labels.csv` chưa tồn tại và là blocker thật của bước classification, (4) siết chặt **eval protocol cho n=140** (baselines + CI thống kê + cluster stability) thay vì chỉ "stratified k-fold", (5) estimate dashboard tăng từ 3 → 6 ngày.
> Nội dung v2 giữ trong git history (commit trước 2026-09-02), không cần lặp lại ở đây.
> Nhịp độ giả định: 6-8h/ngày. Tổng ước tính: **~21-22 ngày** (tăng từ 16-20 — phần tăng là MLOps + labeling + dashboard estimate thực tế hơn, không phải scope mới).

## Cách dùng file này

Đánh dấu `[x]` khi xong. Có phụ thuộc thật — không nhảy bước, TRỪ track MLOps (đánh dấu 🔧) có thể chạy chèn vào bất kỳ lúc nào. Mọi hằng số heuristic (`grace_hours=12`, `half_life_hours=48`...) là **hypothesis ban đầu, chưa calibrate** — không sửa thành "đúng" khi chưa có data thật kiểm chứng.

## Đã hoãn (giữ nguyên từ v2)

- **Giai đoạn 4 — Carousel Generation** (đo tọa độ 28 slide, thứ tự slide chưa rõ)
- **`MomentumIndex`, maturation curve/`Projected72h`** — cần data tích luỹ hàng tháng
- **Multimodal (vision/ASR ảnh/video)** — V2
- **1,285 replies trong training set của classification** — xem "Quyết định còn mở" bên dưới

---

## Quyết định còn mở (cần chốt trước khi tới bước liên quan)

| # | Quyết định | Chốt trước | Ghi chú |
|---|---|---|---|
| Q1 | Replies có vào **vector store / RAG corpus** không (khác với vào training set classification) | Ngày 4 | Loại khỏi training set là hợp lý; nhưng 1,285 replies là 10× dữ liệu cho embedding quality check + RAG retrieval. Đề xuất: **có** cho vector store, **không** cho classification |
| Q2 | Giữ **TF-IDF + LogReg làm baseline** hay bỏ hẳn TF-IDF | Ngày 7 | v2 bỏ TF-IDF như *feature extraction choice* (đúng). Nhưng làm *baseline* thì rất giá trị: chứng minh multilingual embedding thật sự hơn bag-of-words, không chỉ tuyên bố. Đề xuất: **giữ làm baseline** |
| Q3 | Deploy backend ở đâu | Ngày 11 | Render / Fly.io (free tier, nhanh) vs Scaleway / Clever Cloud (hosting Pháp — điểm cộng nhỏ khi nói chuyện với recruiter FR). Frontend vẫn Vercel |
| Q4 | MLflow (local tracking + artifact ra disk) vs chỉ log JSON tự viết | Ngày 4 | MLflow nặng hơn nhu cầu thật của n=140, nhưng chính là tín hiệu MLE mà JD hay yêu cầu. Đề xuất: **MLflow local**, không dựng server riêng |

---

## Ngày 0 — 🩸 Chặn máu: archive + snapshot job (LÀM TRƯỚC MỌI THỨ, ~3-4h)

**Lý do đặt trước Bước 1 cũ:** velocity, longevity, calibration `freshness_weight`, `audience_activity_profile` đều phụ thuộc `insights_snapshots`. Snapshot là **time-series không hồi cứu được** — mỗi ngày trì hoãn là mất ~2 post × N điểm đo, vĩnh viễn. Ngoài ra `data/` hiện **rỗng hoàn toàn (0 file)**: 140 posts đã fetch không được archive ở đâu, `data/raw/` chưa tồn tại.

**Nguyên tắc:** job này KHÔNG chờ SQLite schema hoàn chỉnh. Ghi append-only ra JSONL, ETL vào DB sau (Ngày 1). Schema-light, không bao giờ mất data.

- [ ] `data/raw/` — tạo, thêm vào `.gitignore` (personal data, không commit)
- [ ] `src/ingest/archive.py` — dump 140 posts + 1,285 replies + per-post insights → `data/raw/archive_YYYY-MM-DD.json` (baseline t0, vĩnh viễn, không TTL — khác `data/cache/` TTL 6h)
- [ ] `src/ingest/snapshot.py` — fetch per-post insights → append `data/raw/snapshots/YYYY-MM.jsonl`, mỗi dòng `{post_id, fetched_at (UTC ISO), views, likes, replies, reposts, quotes}`. Idempotent, không ghi đè, lỗi 1 post không làm chết cả run
- [ ] **Tiered cadence** (tiết kiệm quota, dày ở nơi cần):
  - post age ≤ 72h → mỗi 3h (8 lần/ngày) — đây là cửa sổ duy nhất tính được `late_engagement_share`
  - post age 3-14 ngày → 1 lần/ngày
  - toàn bộ post → 1 lần/tuần (sweep)
- [ ] Windows Task Scheduler entry (hoặc `scripts/run_snapshot.ps1`) — ghi log ra `data/raw/snapshot.log`
- [ ] Test: mock `get_post_insights`, verify append không mất dòng + xử lý lỗi 1 post

**Xong khi**: chạy 2 lần cách nhau ≥3h, `snapshots/*.jsonl` có ≥2 dòng cho cùng 1 `post_id` với `fetched_at` khác nhau. Từ đây trở đi data tự tích luỹ trong lúc bạn làm các bước sau.

**Rate limit check**: giới hạn `4,800 × impressions / 24h` rất cao; 140 post × 8 lần/ngày = 1,120 call/ngày — an toàn. Nhưng vẫn nên đo thật ở lần chạy đầu.

## Ngày 1 — `src/models/` + `src/db/` + ETL từ JSONL vào DB

- [ ] `src/models/content_unit.py` — `ContentUnit` dataclass (root, continuations, text_attachment, full_text, media)
- [ ] `src/models/insight_snapshot.py` — `InsightSnapshot` dataclass (post_id, fetched_at, views, likes, replies, reposts, quotes)
- [ ] `src/db/schema.py` — SQLite: `posts`, `content_units`, `insights_snapshots`, `topics`, `post_topic_labels`
- [ ] `src/db/ingest.py` — đọc `data/raw/*.jsonl` + `archive_*.json` → DB, **idempotent** (chạy lại không nhân đôi dòng; UNIQUE constraint trên `(post_id, fetched_at)`)

**Xong khi**: schema tạo được, ETL chạy trên data thật từ Ngày 0, test insert/query + chạy 2 lần không sinh duplicate.

## Ngày 1.5 — 🔧 MLOps #1: CI + Docker (~3-4h)

- [ ] `.github/workflows/ci.yml` — trên push/PR: `uv sync` → `ruff check` → `ruff format --check` → `mypy` → `pytest -q`. Python 3.12
- [ ] `Dockerfile` multi-stage với `uv` (builder cài deps → runtime slim, non-root user)
- [ ] `.dockerignore`
- [ ] README: badge CI + hướng dẫn `docker build` / `docker run`

**Xong khi**: badge CI xanh trên GitHub, `docker run` khởi động được container (chưa cần app hoàn chỉnh — chỉ cần import `src` không lỗi).

**Vì sao ở đây mà không để cuối**: CI chỉ có giá trị khi nó chặn regression *trong lúc* bạn code, không phải khi code đã xong. Và với recruiter, "CI xanh xuyên suốt 200 commit" đọc ra khác hoàn toàn "CI thêm vào commit cuối".

## Ngày 2 — Labeling kit + gán nhãn 140 post

**Blocker thật của Bước classification**: `data/labels/topic_labels.csv` (140 nhãn tay, gold standard) hiện **chưa tồn tại**. Không có nó thì không train, không eval được gì.

- [ ] `scripts/export_for_labeling.py` → CSV: `post_id, timestamp, permalink, text_preview (300 ký tự), label (trống), notes (trống)`
- [ ] **Gán nhãn thủ công 140 post** (việc của tác giả, ~2-3h) — 6 fixed category: Alternance / CV / Entretien / Lifestyle / Data-Insights / Divers. Cho phép `label = "unclear"` — post không rõ topic tốt hơn bị ép vào 1 lớp sai
- [ ] `scripts/validate_labels.py` — class distribution, cảnh báo lớp có < 10 mẫu (với n=140 thì lớp < 10 mẫu gần như không eval được)
- [ ] **Annotation reliability**: hẹn lịch relabel lại 20 post ngẫu nhiên sau ≥7 ngày (không xem nhãn cũ) → tính Cohen's kappa test-retest. Đây là *self-consistency*, không phải inter-annotator agreement — ghi rõ giới hạn này trong report

**Xong khi**: `data/labels/topic_labels.csv` đủ 140 dòng, class distribution đã xem và biết lớp nào thiếu mẫu.

**Vì sao annotation reliability đáng làm**: với n=140 và 1 annotator, con số accuracy đơn lẻ không đáng tin. Có kappa test-retest → bạn biết **ceiling** của model là bao nhiêu, và đó là thứ hiếm thấy trong portfolio junior/mid.

## Ngày 3 — `src/processing/`

- [ ] **Điều tra trước khi code** (~30 phút): đo tỷ lệ reply có `root_post`/`replied_to` trên **toàn bộ 1,285 replies**, không chỉ mẫu `limit=20` (mẫu cũ chỉ 9-10/20 có data). Nếu ~50% reply thiếu parent thì thuật toán nối chuỗi sẽ **sai âm thầm** — cần biết số thật trước khi chọn thuật toán
- [ ] `thread_reconstruction.py` — build `ContentUnit` từ `ThreadsPost` (root) + `get_replies()` (continuations, lọc `is_reply_owned_by_me=True`, nối theo `replied_to`/`root_post`). Nếu thiếu parent nhiều: fallback heuristic (cùng tác giả + timestamp gần nhau) — **đánh dấu rõ unit nào reconstruct bằng fallback**, không trộn lẫn với unit chắc chắn
- [ ] `text.py` — `raw_text` (bất biến) + `normalize_text()` (CHỈ whitespace + URL, KHÔNG strip emoji/hashtag)

**Xong khi**: chạy trên data thật, tạo được ≥1 `ContentUnit` có `continuations` không rỗng; biết chính xác bao nhiêu % unit dùng fallback.

## Ngày 4 — `src/nlp/language.py` + `embeddings.py` + 🔧 MLflow

- [ ] `language.py` — `lingua-py`, `LanguageInfo` (primary_language nullable, detected_languages, confidence, `language_mix_score` liên tục)
- [ ] `embeddings.py` — sentence-transformers multilingual (`bge-m3` / `multilingual-e5-large`) trên `ContentUnit.full_text`. Cache embedding ra `.npy` + lưu `model_name` + `model_revision` + hash của text đầu vào (để biết embedding nào stale khi đổi model)
- [ ] 🔧 MLflow local: log run embedding (model, dim, n_units, thời gian chạy, device) — chốt Q4 trước khi làm
- [ ] Chốt Q1 (replies vào vector store hay không)

**Xong khi**: `language_mix_score` phân biệt được câu thuần Việt (thấp) vs code-switch rõ (cao), không false-positive với từ mượn tech ("deploy", "model", "production"). Kiểm bằng tay ~10 câu tự chọn.

## Ngày 5 — Base indexes (`src/analysis/`)

- [ ] **Sửa** `PostInsights.engagement_rate` (`src/api/models.py`) — thêm `quotes` vào tử số, cập nhật `tests/api/test_models.py`
- [ ] **Guard `views == 0`** cho mọi rate (engagement/virality/conversation) — hiện chưa có, sẽ `ZeroDivisionError` trên post ghost/mới đăng
- [ ] `popularity.py`, `virality.py` (chỉ nhận `insights`), `conversation.py` — theo công thức tại `data-model.md`

**Xong khi**: test pass (kể cả edge case views=0), verify trên 140 post thật, ruff/mypy sạch.

## Ngày 6 — `velocity.py` + `longevity.py` + `freshness.py`

Tới đây snapshot đã tích luỹ ~5-6 ngày → có data thật để verify, không chỉ mock.

- [ ] `velocity.py` — `view_velocity`, `amplification_velocity` giữa 2 snapshot
- [ ] `longevity.py` — `late_engagement_share` (cần snapshot phủ 24h + 72h, chỉ áp dụng post mới từ Ngày 0)
- [ ] `freshness.py` — `freshness_weight(age_hours, grace_hours=12, half_life_hours=48)`, docstring ghi rõ "initial hypothesis, chưa calibrate"

**Xong khi**: velocity tính được cho ≥1 post thật; test pass các edge case (age=0, age=grace_hours, age rất lớn, 2 snapshot cùng timestamp).

## Ngày 7-8 — Fixed-category classification + eval protocol nghiêm

**Ràng buộc chi phối toàn bộ bước này**: n=140, 6 lớp, ~23 mẫu/lớp, embedding 1024 chiều. Đây là chế độ **high-variance**. Một con số accuracy đơn lẻ ở đây là vô nghĩa — giá trị portfolio nằm ở việc xử lý đúng small-data, không nằm ở việc con số cao.

- [ ] **Bậc thang baseline** (mỗi bậc trả lời 1 câu hỏi cụ thể):
  1. Majority class — sàn tuyệt đối
  2. TF-IDF + LogReg — *multilingual embedding có thật sự hơn bag-of-words?* (chốt Q2)
  3. Embedding + nearest-centroid / kNN — *có cần model học được không, hay chỉ cần khoảng cách?*
  4. Embedding + LogReg — baseline tuyến tính
  5. Embedding + SVM-RBF — model chính, *ranh giới phi tuyến có đáng không?*
- [ ] **Eval**: `RepeatedStratifiedKFold(n_splits=5, n_repeats=5)`, metric chính **macro-F1** (không dùng accuracy vì imbalanced), báo cáo mean ± std + **bootstrap CI 95%**, kèm per-class F1 + confusion matrix
- [ ] **Nested CV** cho hyperparameter (C, gamma) — grid NHỎ (3×3), grid lớn trên n=140 là overfit protocol
- [ ] 🔧 MLflow: mỗi baseline = 1 run, log params/metrics/confusion matrix artifact
- [ ] `models/model_card.md` — task, data (n, class distribution, annotator = 1, kappa test-retest), metrics kèm CI, **giới hạn đã biết**, intended use

**Xong khi**: bảng kết quả 5 baseline có CI; **kết luận trung thực** — nếu CI của SVM-RBF trùng CI của LogReg thì viết ra là "không kết luận được model nào hơn với n hiện tại", không cherry-pick.

## Ngày 9 — Unsupervised topic discovery + cluster stability

- [ ] UMAP (→ 3D visualize) + HDBSCAN (cluster trên embedding gốc, `min_cluster_size=5`)
- [ ] **Stability analysis**: chạy lại pipeline với ≥5 random seed khác nhau → pairwise ARI giữa các clustering. 140 điểm rất dễ ra cluster không stable — cần biết số thật
- [ ] So sánh với 6 fixed category (ARI + purity)
- [ ] KMeans + silhouette làm baseline clustering thứ hai
- [ ] LLM (Claude) label mỗi cluster → tên + mô tả **tiếng Anh**

**Xong khi**: có cluster + tên tiếng Anh; biết % điểm bị HDBSCAN gán noise và ARI stability giữa các seed. Nếu phần lớn là noise → báo cáo đúng như vậy, kèm giải thích n quá nhỏ; đó vẫn là kết quả có giá trị.

## Ngày 10 — `topic_affinity.py` + `timing.py`

- [ ] `topic_affinity_score(topic_id, window_days)` — report_window 7d/14d/30d/90d, ưu tiên 30d/90d
- [ ] `audience_activity_profile()` — group velocity theo publish_hour + hour_since_publish
- [ ] **Verify live** `get_follower_demographics(breakdown="country")` (đã build, chưa từng gọi thật) — đối chiếu hypothesis timezone VN/Pháp

**Xong khi**: có empirical evidence (không chỉ giả định) cho pattern giờ audience active, hoặc kết luận rõ là data chưa đủ.

## Ngày 11 — `src/pipeline/analytics.py` + `src/main.py` (FastAPI)

- [ ] `src/pipeline/analytics.py` — batch job orchestrate ingestion → processing → nlp → analysis → ghi DB (KHÔNG chạy trong request)
- [ ] `src/main.py` — FastAPI đọc từ SQLite, endpoint: `/posts`, `/metrics`, `/topics`, `/timing`, `/health`
- [ ] Test integration cho ≥2 endpoint

## Ngày 11.5 — 🔧 MLOps #2: Deploy backend (~3-4h)

- [ ] Chốt Q3, deploy Docker image (Render / Fly.io / Scaleway)
- [ ] `/health` endpoint + uptime check
- [ ] GitHub Actions: build + deploy on git tag
- [ ] README: link API docs công khai (`/docs`)

**Xong khi**: URL public trả `/health` 200. Đây là artifact quan trọng nhất với recruiter — link chạy được, không phải screenshot.

## Ngày 12 — RAG (`src/generation/rag.py`)

- [ ] Vector store (Chroma) — tái dùng embedding từ Ngày 4, KHÔNG tính lại
- [ ] Retrieval top-k + Claude generation, grounded trên content thật đã đăng
- [ ] Eval nhẹ: ~10 query tự soạn, kiểm retrieval có kéo đúng post liên quan không (manual relevance judgment, ghi rõ là subjective)

## Ngày 13-18 — Dashboard (Next.js) — *estimate tăng từ 3 → 6 ngày*

- [ ] **13**: setup Next.js + design tokens từ `design-system.md` + layout/sidebar + component library
- [ ] **14**: Overview (followers, avg engagement, top posts) + Analytics (trend theo report_window)
- [ ] **15**: Heatmap timing 2 timezone + Topic Explorer (3D scatter Plotly)
- [ ] **16**: Content Library + Settings
- [ ] **17**: Generate Content page (nối RAG)
- [ ] **18**: Mobile responsive + scroll animation (Intersection Observer) + bug fix

Toàn bộ copy **tiếng Anh**.

**Vì sao 6 ngày**: v2 ước 3 ngày cho setup + component library + 5 trang + 3D Plotly + responsive theo một design system pixel-level đã viết sẵn. Không khả thi ở 6-8h/ngày. Nếu cần cắt: bỏ Content Library + Settings trước, giữ Overview/Analytics/Topic Explorer/Generate.

## Ngày 19-20 — Content generation + calibrate giọng văn ⚠️ rủi ro lịch cao nhất

- [ ] Đọc `Content/Scripts/*.docx` → extract giọng văn thành few-shot examples
- [ ] Prompt + RAG context động
- [ ] Vòng lặp calibrate: generate → tác giả đánh giá → sửa prompt. **Không có metric tự động cho "đúng giọng văn"** — đây là lý do bước này rủi ro nhất, cần chấp nhận đánh giá chủ quan và ghi rõ

## Ngày 21 — Buffer + Portfolio narrative

- [ ] `README.md` **tiếng Anh**: problem → approach → results (bảng có CI) → architecture diagram → live demo link → limitations
- [ ] Architecture diagram (Mermaid, commit vào repo)
- [ ] Tổng hợp decisions log thành 1 section ngắn tiếng Anh — đây là điểm mạnh nhất của repo, đừng để nó chỉ nằm trong `docs/claude/`
- [ ] Bug fix tồn đọng

---

## Portfolio deliverables checklist (kiểm ở Ngày 21)

- [ ] README tiếng Anh có problem/approach/results/limitations
- [ ] CI badge xanh, lịch sử CI xuyên suốt
- [ ] Dockerfile + image build được
- [ ] API public chạy được (`/docs`)
- [ ] Dashboard deploy trên Vercel
- [ ] MLflow runs so sánh ≥5 baseline, bảng kết quả có bootstrap CI
- [ ] Model card có class distribution + kappa test-retest + limitations
- [ ] Architecture diagram
- [ ] Decisions log bản tiếng Anh

## Nếu còn thời gian

Giai đoạn 4 — Carousel Generation (~25-40h). Hoặc: calibrate `grace_hours`/`half_life_hours` bằng snapshot data đã tích luỹ (~3 tuần data tại thời điểm đó) — việc này có giá trị portfolio cao hơn carousel, vì nó biến hằng số hypothesis thành hằng số có evidence.
