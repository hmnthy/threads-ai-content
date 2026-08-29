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
│   │   ├── Entretien/         # 11 slide templates — chủ đề phỏng vấn
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
│   ├── analysis/              # Engagement calc, virality scoring (CHƯA VIẾT)
│   ├── generation/            # AI text generation — Claude API (CHƯA VIẾT)
│   ├── carousel/              # Pillow-based image composition (CHƯA VIẾT)
│   │   └── fonts/
│   │       └── Google_Sans/   # Font Việt hóa đã tải về
│   └── dashboard/             # Frontend Next.js app (CHƯA VIẾT)
│       ├── components/
│       ├── pages/
│       └── styles/
│
├── tests/
│   └── api/                   # Test cho src/api/ — 27 test, chạy `uv run pytest`
│
├── data/
│   ├── cache/                 # API response cache (JSON, tối đa 6 giờ)
│   └── processed/             # Cleaned & classified post data
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
| Database | SQLite (dev) → PostgreSQL (prod) |
| Virality scoring | Weighted formula thuần Python — không dùng ML |
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

---

## Roadmap tính năng theo module

### Module 1 — Data Pipeline & Analysis (`src/api/` + `src/analysis/`)
- Fetch toàn bộ posts + metrics, cache local (tránh rate limit)
- Tính engagement rate: `(likes + replies + reposts) / views * 100`
- Phân loại posts theo chủ đề (keyword matching + Claude classification)
- Timeline performance: hiệu suất theo thời gian, giờ đăng tốt nhất
- Virality Index — công thức đầy đủ tại [`data-model.md`](data-model.md#virality-index)

### Module 2 — Dashboard (`src/dashboard/`)
- Overview: followers growth, avg engagement rate, top posts
- Content map: scatter plot chủ đề × engagement
- Heatmap: ngày/giờ đăng tốt nhất
- Topic gap analysis: chủ đề nào chưa được khai thác
- UI spec đầy đủ tại [`design-system.md`](design-system.md)

### Module 3 — AI Content Generation (`src/generation/`)
- Workflow + quy tắc đầy đủ tại [`dev-rules.md`](dev-rules.md#content-generation-text)

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
