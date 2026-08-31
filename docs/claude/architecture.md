# Architecture — Threads AI Content

> Đọc khi: cần biết cấu trúc thư mục, tech stack, các quyết định kỹ thuật đã chốt và lý do, hoặc workflow tổng thể của pipeline.
> Xem thêm: [`CLAUDE.md`](../../CLAUDE.md) cho mission/status, [`data-model.md`](data-model.md) cho Threads API, [`design-system.md`](design-system.md) cho UI, [`dev-rules.md`](dev-rules.md) cho setup/workflow rules.

---

## Cấu trúc thư mục

```
threads-ai-content/
├── CLAUDE.md
├── .env                       # Không commit — API tokens
├── .env.example               # Template env (có thể commit)
├── .gitignore
├── .pre-commit-config.yaml    # ruff + mypy hooks
├── .python-version            # Pin 3.12 cho uv
├── pyproject.toml             # Deps + config ruff/mypy/pytest (thay requirements.txt)
├── uv.lock                    # Lockfile — commit vào git
├── .venv/                     # Không commit — tạo bởi `uv sync`
│
├── docs/
│   ├── claude/                 # Tài liệu kiến trúc chi tiết cho Claude — đọc theo nhu cầu, không nạp sẵn
│   │   ├── architecture.md     # File này
│   │   ├── data-model.md       # Threads API integration, virality formula, topic mapping
│   │   ├── design-system.md    # UI/design system đầy đủ
│   │   └── dev-rules.md        # Setup commands, env vars, content/carousel workflow rules
│   ├── design/
│   │   └── dashboard-reference.png   # Design mockup tham khảo UI
│   ├── project-summary.md     # Tóm tắt trạng thái project
│   └── next-steps.md          # Việc cần làm tiếp theo + resume prompt
│
├── Content/                   # Assets gốc của tác giả — KHÔNG sửa
│   ├── Content - Photo carousel/
│   │   ├── Alternance/        # 7 slide templates — chủ đề alternance/thực tập
│   │   ├── CV/                # 9 slide templates — chủ đề CV/hồ sơ
│   │   ├── Entretien/         # 12 slide templates — chủ đề phỏng vấn
│   │   └── Photos/            # Ảnh/video gốc của tác giả
│   ├── Project - Cocoon/      # Tài liệu hợp tác thương hiệu (tham khảo tone)
│   └── Scripts/               # Draft content gốc — nguồn học giọng văn tác giả
│       ├── Content DATA.docx
│       ├── Content Divers.docx
│       ├── Content Đi đâu chơi gì - Corrigé.docx
│       ├── Framework_Video.xlsx
│       └── Tiktok Thy - Dàn bài.docx
│
├── src/
│   ├── __init__.py
│   ├── api/                   # Threads API client + auth (HOÀN TẤT, có test)
│   │   ├── __init__.py        # Public exports
│   │   ├── auth.py            # Load credentials, refresh long-lived token, expiry warning
│   │   ├── client.py          # ThreadsClient (httpx AsyncClient) + ThreadsAPIError
│   │   ├── endpoints.py       # get_posts, get_post_insights, get_account_insights, get_user_info
│   │   ├── models.py          # Pydantic: ThreadsPost, PostInsights, AccountInsights, UserInfo, MediaType
│   │   └── cache.py           # JSON cache TTL 6h tại data/cache/
│   ├── models/                # ContentUnit, InsightSnapshot (ThreadsPost đã có ở src/api/models.py) — CHƯA VIẾT
│   ├── processing/            # thread_reconstruction.py, text.py (raw+normalized) — CHƯA VIẾT
│   ├── nlp/                   # language.py (lingua-py), embeddings.py, topics.py (UMAP+HDBSCAN) — CHƯA VIẾT
│   ├── analysis/              # engagement.py xong (bucketing utils); popularity/virality/conversation/
│   │                          # velocity/longevity/freshness/topic_affinity/timing.py CHƯA VIẾT
│   ├── db/                    # SQLite schema + vector store (Chroma/FAISS) — CHƯA VIẾT
│   ├── pipeline/               # analytics.py — batch job orchestrate ingestion→processing→nlp→analysis→db — CHƯA VIẾT
│   ├── generation/            # AI text generation — Claude API + RAG (CHƯA VIẾT)
│   ├── carousel/              # Pillow-based image composition (CHƯA VIẾT)
│   │   └── fonts/
│   │       └── Google_Sans/   # Font Việt hóa đã tải về
│   └── dashboard/             # Frontend Next.js app (CHƯA VIẾT)
│       ├── components/
│       ├── pages/
│       └── styles/
│
├── tests/
│   ├── api/                   # Test cho src/api/ — 27 test, chạy `uv run pytest`
│   └── analysis/              # Test cho src/analysis/ — 8 test
│
├── data/
│   ├── cache/                 # API response cache (JSON, tối đa 6 giờ)
│   ├── processed/             # Cleaned & classified post data
│   └── labels/                # topic_labels.csv — nhãn tay 140 post (gold-standard, user tự gán)
│
└── output/
    └── carousel_YYYY-MM-DD_topic/   # Generated carousel PNG sequences
```

---

## Tech Stack đã chốt

| Layer | Công nghệ |
|-------|-----------|
| Backend / API | **Python (FastAPI)** — ưu tiên duy nhất; Next.js API routes chỉ dùng cho BFF dashboard nếu cần |
| Package manager | **uv** + `pyproject.toml` (thay pip/requirements.txt) — lockfile `uv.lock`, venv tại `.venv/` |
| Threads API client | `httpx` (async, dùng với FastAPI) |
| Validation / models | `pydantic` v2 |
| AI / LLM | Claude API (`claude-sonnet-4-6`) với prompt caching |
| Dashboard | **Next.js** + Recharts / shadcn/ui — quyết định final, deploy trên Vercel |
| Image generation | **Pillow** (Python) — overlay text lên template PNG có sẵn |
| Font carousel | **Google Sans** (Việt hóa) — đã tải tại `src/carousel/fonts/Google_Sans/` |
| Database | SQLite (dev) → PostgreSQL (prod) — bảng `posts`, `content_units`, `insights_snapshots`, `topics`, `post_topic_labels` |
| Metric scoring | 6 index tách biệt (popularity/engagement/virality/conversation/velocity/longevity) + contextual score (freshness/topic_affinity/timing) — không gộp 1 công thức, xem `data-model.md` |
| Language ID | `lingua-py` (không phải `langdetect`) — confidence-aware, robust hơn trên short/mixed text |
| NLP feature extraction | `sentence-transformers` multilingual (`bge-m3` hoặc `multilingual-e5-large`) — thay TF-IDF/tokenizer riêng tiếng Việt vì content trộn VI/FR/EN |
| Fixed-category classification | `SVM-RBF` (chính) + `LogisticRegression` (baseline so sánh), sklearn, stratified k-fold CV |
| Topic discovery (unsupervised) | `UMAP` (giảm chiều → 3D visualize) + `HDBSCAN` (cluster) |
| Vector store / RAG | Chroma hoặc FAISS — tái dùng embedding đã tính cho clustering |
| Code quality | ruff (lint + format), mypy (strict), pytest + pytest-asyncio + respx, pre-commit |

---

## Quyết định quan trọng đã chốt

| Quyết định | Lý do |
|-----------|-------|
| Backend duy nhất là FastAPI, không dùng Node.js | Toàn stack Python, nhất quán, dễ maintain |
| Dùng `httpx` thay `requests` | Async native — chạy tốt với FastAPI |
| Không dùng ML cho virality scoring | Dữ liệu chưa đủ, weighted formula là đủ và giải thích được |
| Font Google Sans cho carousel | Hỗ trợ tiếng Việt, miễn phí, đã có file `.ttf` |
| Pillow thay Canva/Figma API | Chạy offline, pixel-perfect với template PNG gốc |
| Scroll animation dùng Intersection Observer | Không cần thư viện nặng (AOS/GSAP), performance tốt hơn |
| Mobile responsive bắt buộc | Dashboard phải dùng được trên điện thoại |
| Cache TTL 6 giờ | Tránh gọi API thừa, tránh rate limit |
| Threads API chỉ cung cấp data của chính chủ (Phase 1) | Standard Access không cho crawl feed người khác ở quy mô có ý nghĩa — xem Phase 2 trong `CLAUDE.md` cho hướng mở rộng |
| Quyền đọc metrics/insights là `threads_manage_insights`, **không phải** `threads_manage_replies` | Sửa lại quyết định sai trước đó (2026-04-30): `threads_manage_replies` chỉ dùng để quản lý/kiểm duyệt reply, không liên quan đọc engagement. `threads_read_engagement` không tồn tại trong Threads API |
| `reach` và `impressions` không có trong Threads API | Khác Instagram API — không tính được CPM |
| Dùng `uv` thay `pip`/`poetry` | Chuẩn 2026, nhanh hơn, lockfile + quản lý venv tích hợp |
| Test song song với từng module + ruff/mypy strict/pre-commit từ đầu | Theo yêu cầu nâng chuẩn "senior ML/AI Engineer 2026" — quyết định 2026-08-28 |
| CLAUDE.md tách thành `docs/claude/*.md`, chỉ trỏ đường dẫn (không `@import`) | CLAUDE.md gốc đã hơn 500 dòng và sẽ tiếp tục phình to qua các giai đoạn; `@import` nạp sẵn mỗi phiên như để nguyên 1 file, còn plain reference để Claude tự đọc file liên quan theo đúng task — quyết định 2026-08-29 |
| Dashboard dùng Next.js, không dùng Streamlit | Design system (`design-system.md`) đòi hỏi kiểm soát CSS/JS hoàn toàn — custom donut chart (Virality Score Ring), scroll-triggered animation qua Intersection Observer, component patterns pixel-level. Streamlit render trong sandbox riêng, muốn custom sâu phải hack qua `st.components.v1.html`, khó maintain (đã thử năm 2025, không đủ linh hoạt). Deploy trên Vercel (đã có GitHub App liên kết sẵn) — quyết định 2026-08-29 |
| Timeline analysis (`engagement_by_hour`/`by_weekday`) parametrize theo `timezone` thay vì hard-code 1 múi giờ, hoặc viết riêng 2 hàm cho Pháp/VN | Audience kênh trải cả Pháp và Việt Nam. Threads API không expose engagement theo viewer timezone/country ở mức per-post, nên không thể tách thật theo audience — chỉ có thể convert cùng 1 timestamp sang nhiều múi giờ để so sánh. Parametrize (thay vì duplicate hàm) tránh lặp code khi cần thêm múi giờ khác sau này. Dùng `zoneinfo` (chuẩn thư viện, tự xử lý DST của Paris) thay vì `pytz` — cần thêm `tzdata` vào dependencies vì Windows không có sẵn IANA timezone database — quyết định 2026-08-29 |
| `topics.py` redesign: pipeline NLP thật (embedding → SVM-RBF/LogReg + UMAP/HDBSCAN) thay vì "keyword matching + Claude classification" | Dự án là portfolio thể hiện chuyên môn NLP/ML 2026, không chỉ cần nhãn topic dùng được. Claude classification là black-box, không đi qua tokenization/vector hoá nào — không tương thích mục tiêu học thuật/portfolio. Quyết định 2 hệ thống song song: fixed-category (SVM-RBF chính, LogReg baseline, cho carousel routing) + cluster khám phá (UMAP+HDBSCAN, cho analytics/gap analysis) — quyết định 2026-08-30 |
| Bỏ `underthesea` (Vietnamese-only tokenizer), dùng sentence-transformers multilingual | Content trộn VI/FR/EN tự nhiên — tokenizer riêng tiếng Việt sẽ segment sai phần tiếng Pháp/Anh. Model multilingual (bge-m3/multilingual-e5-large) tự xử lý đa ngôn ngữ ở tầng embedding — quyết định 2026-08-30 |
| Batch pipeline (embedding/clustering/trend) tách riêng khỏi FastAPI serving layer | FastAPI chỉ đọc kết quả đã tính sẵn từ SQLite, không load model transformer mỗi request (anti-pattern, chậm). Pipeline là batch job chạy riêng, ghi kết quả vào DB — kiến trúc chuẩn hệ thống ML production (tách batch compute khỏi serving) — quyết định 2026-08-30 |
| RAG tái dùng chung vector store với clustering, không xây hạ tầng riêng | Bước feature extraction đã tạo embedding cho mọi post — dùng lại đúng vector store đó cho RAG retrieval, tránh trùng lặp hạ tầng — quyết định 2026-08-30 |
| 1,285 replies chưa đưa vào NLP pipeline V1 | Replies mang tính tương tác/hội thoại, không phải content topic thuần — phù hợp hướng phân tích khác (graph tương tác) sau này hơn là pipeline topic hiện tại — quyết định 2026-08-30 |
| Velocity (Δengagement/Δtime) cần snapshot định kỳ, không hồi cứu được cho 140 post cũ | Threads API chỉ trả tổng số liệu tại thời điểm gọi, không có history — đây là giới hạn dữ liệu thật của API, không phải giới hạn kỹ thuật của hệ thống — quyết định 2026-08-30 |
| Output hướng ra ngoài (dashboard UI, topic label/description do LLM sinh, RAG response) bắt buộc tiếng Anh; nội bộ dự án (docs, code comment) giữ tiếng Việt | Dự án là portfolio cho người ngoài xem — sản phẩm cuối cần tiếng Anh; trao đổi/tài liệu nội bộ giữ tiếng Việt cho thuận tiện làm việc — quyết định 2026-08-30 |
| `virality_index` tách thành 6 index riêng (popularity/engagement/virality/conversation/velocity/longevity) + contextual score (freshness/topic_affinity/timing), bỏ `recency_boost`/`length_penalty`/`topic_trend_score` gộp chung | User chỉ ra 2 lỗi phương pháp luận: (1) hằng số heuristic không có evidence, (2) trộn intrinsic performance với explanatory variables vào 1 công thức. Portfolio NLP/ML chuẩn 2026 cần tách bạch, mọi hằng số ghi rõ là hypothesis chưa calibrate — quyết định 2026-08-30 |
| `freshness_weight()` tách hẳn khỏi `virality_index`, chỉ dùng cho "đang hot ngay bây giờ" | Trộn recency vào virality_index xoá sổ sai semantic: post 20 ngày trước vẫn có thể là bài viral nhất quý. Velocity/momentum quan trọng hơn recency đơn thuần vì audience VN + timezone Pháp tạo confounding factor (giờ đăng Pháp buổi tối = giờ VN đang ngủ, low engagement 6h đầu không đồng nghĩa content dở) — quyết định 2026-08-30 |
| `topic_trend_score` đổi tên `topic_affinity_score`; tách `post_maturity_window` (0-72h) khỏi `report_window` (7d/14d/30d/90d) | Không đo được "trend trên Threads" (Standard Access, ~2 post/ngày). Chỉ đo được hiệu suất lịch sử CỦA CHÍNH KÊNH theo topic — 2 khái niệm thời gian khác nhau không được trộn — quyết định 2026-08-30 |
| Thêm `ContentUnit` (root + self-reply continuations + text_attachment), tách khỏi `ThreadsPost` raw ingestion | Thread dài trên Threads là chuỗi self-reply (5-15 post) + text attachment tới 10.000 ký tự (từ 09/2025) — 1 `ThreadsPost` đơn lẻ không đại diện đúng "1 content". Field `root_post`/`replied_to`/`is_reply_owned_by_me` đã verify live 2026-08-30 (đủ để reconstruct). Audience reply KHÔNG gộp vào content — là tín hiệu engagement riêng — quyết định 2026-08-30 |
| Đổi `langdetect` → `lingua-py`; `has_french_mix: bool` → `language_mix_score: float`; bỏ aggressive text cleaning trước embedding | Áp dụng paper "Challenges of Computational Processing of Code-Switching": document-level LID trên short text kém tin cậy, LID không nên gate/route pipeline downstream (error propagation), ranh giới code-switch vs từ mượn (VD "deploy"/"model") không rõ ràng nên cần continuous score thay vì boolean, và aggressive cleaning phá semantic signal (emoji/hashtag mang tín hiệu thật) — quyết định 2026-08-30 |
| `PostInsights.engagement_rate` (src/api/models.py) sửa thêm `quotes` vào tử số | Công thức cũ `(likes+replies+reposts)/views` thiếu `quotes` — phát hiện khi thiết kế lại `engagement_rate()` nhất quán với `virality_index`/`conversation_rate` mới, cần sửa cả `tests/api/test_models.py` — quyết định 2026-08-30 |
| Metric "shares" (S) trong công thức Engagement/Virality Rate KHÔNG dùng | Verify live 2026-08-28 xác nhận post-level insights Threads chỉ có `views, likes, replies, reposts, quotes` — không có field "shares" riêng biệt — quyết định 2026-08-30 |
| Repo này (`hmnthy/threads-ai-content`) giữ **Private vĩnh viễn làm "working repo"** — đầy đủ lịch sử thật kể cả các đoạn tranh luận/redesign; khi cần bản public sẽ squash/curate sang 1 repo public riêng | Giá trị portfolio nằm ở quá trình tư duy (docs, decisions log, commit message) chứ không phải việc giấu AI có tham gia hay không — không cần "dọn sạch" lịch sử làm việc thật. Repo public sau này (nếu có) sẽ là bản curated riêng, không phải chính repo này — quyết định 2026-08-30 |
| Git commit trong repo này **không thêm trailer** `Co-Authored-By: Claude...` | Xem dòng "Quy tắc tuyệt đối" trong `CLAUDE.md`. Lịch sử commit trước quyết định (`31adcbc`, `3eceabe`) giữ nguyên, không rewrite/force-push — rủi ro không đáng đổi cho 1 sửa đổi mang tính thẩm mỹ — quyết định 2026-08-30 |
| `.pre-commit-config.yaml` — hook `mypy` đổi từ `repo: mirrors-mypy` (tự tạo venv riêng trong `~/.cache/pre-commit/`) sang `repo: local` trỏ thẳng `.venv/Scripts/python.exe -m mypy` | Application Control Policy trên máy chặn ngẫu nhiên các file `.dll` biên dịch của mypy khi load từ `~/.cache/pre-commit/` (nhiều khả năng do policy coi thư mục cache/tải-về là kém tin cậy hơn `.venv` của project) — lỗi tái diễn ở các module mypy khác nhau mỗi lần (`error_formatter`, `semanal_infer`, `indirection`...), không phải lỗi code. Ban đầu định dùng `entry: uv run mypy` nhưng `uv` không có trên PATH trong terminal thật của user (`uv.exe` cài qua `pip install --user` nằm ở `AppData\Roaming\Python\PythonXXX\Scripts`, không tự thêm vào PATH) — đổi sang trỏ thẳng `.venv/Scripts/python.exe` để không phụ thuộc `uv` có trên PATH hay không — quyết định 2026-08-31 |

---

## Roadmap tính năng theo module

### Module 1 — Data + NLP Foundation (`src/api/` + `src/analysis/` + `src/db/`)
- Fetch toàn bộ posts + metrics, cache local (tránh rate limit)
- Tính engagement rate: `(likes + replies + reposts) / views * 100`
- NLP pipeline thật: embedding (sentence-transformers multilingual) → fixed-category classification (SVM-RBF + LogReg baseline) song song với unsupervised topic discovery (UMAP + HDBSCAN + LLM labeling) — chi tiết đầy đủ tại [`data-model.md`](data-model.md#nlp-pipeline)
- Trend/velocity scoring theo topic × time window (day/week/month)
- Timeline performance: hiệu suất theo thời gian, giờ đăng tốt nhất
- Virality Index — công thức đầy đủ tại [`data-model.md`](data-model.md#virality-index)

### Module 2 — Dashboard (`src/dashboard/`)
- Overview: followers growth, avg engagement rate, top posts
- Topic Explorer: 3D scatter (UMAP + Plotly) hiển thị cluster khám phá được, so sánh với 6 fixed-category
- Heatmap: ngày/giờ đăng tốt nhất (2 timezone Pháp + VN)
- Trend chart: top topics theo day/week/month
- Topic gap analysis: chủ đề nào chưa được khai thác
- UI spec đầy đủ tại [`design-system.md`](design-system.md) — toàn bộ copy tiếng Anh

### Module 3 — AI Content Generation (`src/generation/`)
- RAG-assisted: retrieval trên vector store (post/reply embedding) + Claude generation, grounded trên content thật đã đăng
- Workflow + quy tắc đầy đủ tại [`dev-rules.md`](dev-rules.md#content-generation-text), thiết kế RAG tại [`data-model.md`](data-model.md#rag-retrieval-augmented-generation)

### Module 4 — Carousel Generation (`src/carousel/`)
- Workflow + quy tắc đầy đủ tại [`dev-rules.md`](dev-rules.md#carousel-generation-image)

---

## Workflow tổng thể

```
[Fetch Threads API]
       ↓
[Cache & Process data]
       ↓
[Dashboard + Analytics]
       ↓
[Topic Gap Analysis]
       ↓
[AI Content Ideas (3-5 ideas)]
       ↓
[Generate 3 versions per idea + Virality Index]
       ↓
[Author Reviews & Selects]
       ↓
[Author Approves] ── (text only) ──→ [Done]
       │
       └─ (muốn carousel) ──→ [Map template] ──→ [Generate slides] ──→ [Export PNG]
                                                          ↓
                                                  [Author Final Review]
                                                          ↓
                                                  [Manual post lên Threads]
```
