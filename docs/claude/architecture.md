# Architecture — Unthreaded

> Đọc khi: cần cấu trúc thư mục, tech stack, hoặc luồng dữ liệu tổng thể.
> Lý do của từng lựa chọn: `docs/decisions/` (ADR) + `docs/decisions/legacy-log.md` (trước 2026-09-30). Kế hoạch: `docs/roadmap.md`.

## Cấu trúc thư mục

```
threads-ai-content/
├── CLAUDE.md                  # ≤80 dòng: mission, quy tắc tuyệt đối, bản đồ tài liệu
├── .claude/
│   ├── settings.json          # hooks, attribution tắt, deny .env
│   ├── hooks/                 # session_status / guard_commit / ruff_on_edit / adr_written / tests_only / notify+toast; SubagentStart/Stop (settings.json) → scripts/review_gate.py ghi dấu review vào `<git-common-dir>/claude-review/` (chung mọi worktree)
│   ├── rules/                 # quy tắc theo đường dẫn (paths:) — chỉ nạp khi chạm đúng mảng code
│   ├── agents/                # code-reviewer, qa-tester, researcher, consistency-auditor, copy-reviewer, promise-auditor
│   └── skills/                # /prime /checkpoint /record-decision /decision-sweep /new-rq /recluster /wt /git-flow /promise-audit ui-lookup
├── .mcp.json                  # context7 + huggingface
├── docs/
│   ├── status.md              # trạng thái hiện tại (≤60 dòng)
│   ├── roadmap.md             # phase C → F + cổng chatbot
│   ├── decisions/             # ADR 1 file/quyết định + legacy-log.md + invariants.toml (sổ luật nhất quán)
│   ├── claude/                # tài liệu tham chiếu: architecture, data-model, design-system, dev-rules
│   ├── rq/                    # câu hỏi nghiên cứu RQ-xx (roadmap D, chưa tạo)
│   ├── research/              # PRIVATE, gitignored — market scan, methodology
│   ├── archive/               # plan/sprint cũ, giữ nguyên văn
│   ├── design/ (handoff, brief, ui-contract — ADR-0020) · screenshots/
├── src/
│   ├── api/                   # Threads Graph API client (httpx async, pydantic, cache TTL 6h, pagination)
│   ├── models/                # ContentUnit, InsightSnapshot
│   ├── processing/            # thread_reconstruction (root + continuation), text (NFC, dấu thanh)
│   ├── nlp/                   # language (CMI + LID cấp từ), embeddings (bge-m3), topics (UMAP+HDBSCAN+Claude label), topic_profile (c-TF-IDF trên từ tách bằng underthesea, bài đại diện, ARI), stopwords (stopword từ khoá có nhãn, ADR-0022), topic_identity (danh tính cụm bền, ADR-0018)
│   ├── analysis/              # 6 index (share_rate…) + reach (tầng, ADR-0012) + stats/significance/topic_comparison/reply_thread/topic_affinity
│   ├── db/schema.py           # SQLite: posts, content_units, insights_snapshots, account_daily_views, topics, post_topic_labels, embeddings, cluster_runs, topic_label_history, topic_comparison_runs, topic_comparisons
│   ├── pipeline/              # ingest, snapshot, daily_views, scheduled_job + nlp_cluster_job (cron, pythonw — ADR-0013), job_log, cầu nối clustering Win↔WSL2 (bỏ ở Phase C), compare_topics (bước cuối job NLP, ADR-0023)
│   ├── main.py                # FastAPI — chỉ đọc SQLite, không load model trong request
│   └── dashboard/             # Next.js 16 + Tailwind v4: landing `/` + `/overview` `/analytics` `/topics`;
│                              # scripts/screenshots.mjs (Playwright + Edge → docs/screenshots/)
├── tools/ui-ux-pro-max/       # CLI tra cứu UI (vendored) — gọi qua skill ui-lookup
├── scripts/                   # consistency/check.py (cảnh sát nhất quán), precommit/ (wrapper dashboard), job_health.py (sức khoẻ cron), configure_jobs.ps1 (cấu hình Task Scheduler: Action, lịch, cờ pin), snapshot_coverage.py (độ phủ chuỗi snapshot — nguồn số liệu giới hạn lấy mẫu, ADR-0017), topic_identity_eval.py (thí nghiệm quy tắc danh tính cụm, ADR-0018), git_hygiene.py (nhắc quy ước git ở hook đầu phiên, ADR-0019), review_gate.py (cổng review tầng 2 ADR-0015: ghi dấu + kiểm ở git hook pre-commit)
├── tests/                     # pytest (marker slow/live), respx mock HTTP
├── .github/workflows/ci.yml   # CI: chạy lại các cổng trên máy sạch (ADR-0014)
├── data/                      # gitignored: threads.db, logs/, cache/, raw/
└── content/                   # gitignored: asset cá nhân của tác giả
```

## Tech stack

| Layer | Công nghệ | Trạng thái |
|---|---|---|
| Backend / API | FastAPI + uvicorn | Live |
| Package manager | uv + `pyproject.toml` + `uv.lock` | Live |
| Threads API client | httpx (async) | Live |
| Validation | pydantic v2 | Live |
| Database | SQLite (`data/threads.db`) | Live |
| Language ID | lingua-py + Code-Mixing Index (Gambäck & Das 2014) | Live |
| Embedding | sentence-transformers `BAAI/bge-m3` (1024D, 8.192 token, MIT) | Live, chạy trong WSL2 |
| Topic discovery | UMAP (3D) + HDBSCAN (`leaf`, `min_cluster_size=4`, `n_neighbors=8` — calibrate lại 2026-10-01, ADR-0004) | Live, re-cluster hằng ngày |
| LLM | Claude API `claude-sonnet-5-5` (ADR-0016) — CHỈ đặt tên cluster (tiếng Anh) | Live |
| Thống kê | median/IQR, Brunner-Munzel hoán vị + Cliff's δ kèm CI + Holm (numpy/scipy, ADR-0023) — so sánh topic vs phần còn lại tính trong job NLP, landing live (`GET /topics/comparisons`); trang Topics: next (Việc 4) | Live |
| Dashboard | Next.js 16 + Tailwind v4 + chart SVG tự dựng + Plotly (bản đồ topic) + Phosphor icons | Live — công khai tại https://unthreaded-analytics.vercel.app (mục "Deploy") |
| Hosting | Vercel (Hobby): 2 project từ cùng repo + Vercel Blob riêng tư cho bản sao DB (ADR-0025) | Live từ 2026-10-28 |
| Knowledge base | SQLite FTS5 (BM25) + dense numpy + RRF + `bge-reranker-v2-m3` | Roadmap E |
| Supervised classifier | bậc thang baseline → SVM-RBF (RQ-08) | Roadmap D |
| Chất lượng code | ruff, mypy strict, pytest; pre-commit chặn: ruff, mypy, sổ luật nhất quán (toàn repo, `--commit`), cổng review tầng 2 (chỉ commit của Claude, ADR-0015), pytest nhanh, eslint+tsc, commit-msg | Live |
| CI | GitHub Actions (`.github/workflows/ci.yml`: job py + web, ADR-0014) | Live — chạy lần đầu 2026-10-05 (PR #1: `web` đỏ vì `LayoutProps` → `67c3bf8` → xanh); chỉ chạy khi mở/cập nhật PR, push vào `main` hoặc chạy tay (Roadmap G, ADR-0019) |

## Luồng dữ liệu

```
Threads Graph API ──(Task Scheduler, 4h, pythonw)──► src/pipeline/scheduled_job
        │   posts + replies + per-post insights + account daily views
        ▼
SQLite data/threads.db ◄──(hằng ngày 12:30: src/pipeline/nlp_cluster_job)── export → WSL2 embed+cluster → import+Claude label → compare (topic vs phần còn lại, ADR-0023)
        │
        ├──► local: FastAPI src/main.py (uvicorn :8000) ──► Next.js dashboard (:3000)
        │
        └──(cuối MỖI job: src/pipeline/publish.py — backup → journal_mode=DELETE)──► Vercel Blob riêng tư `threads.db`
                                                                                      │ (đọc ở request đầu, OIDC; hỏi lại ETag mỗi 5 phút)
                                                                                      ▼
                    Vercel project `unthreaded-api` (FastAPI chỉ đọc, `mode=ro`) ──► Vercel project `unthreaded` (Next.js, landing + 3 tab)

Đã có (ADR-0004): reply_role + embeddings lưu trong SQLite + hồ sơ cụm (cluster_runs). Roadmap: toàn bộ Python chạy trong WSL2 (C) → knowledge base + /kb/search (E)
```

## Deploy (ADR-0025, live từ 2026-10-28)

| Phần | Ở đâu | Vai trò |
|---|---|---|
| Trang công khai | Vercel project `unthreaded`, root `src/dashboard` → **https://unthreaded-analytics.vercel.app** (`unthreaded-psi.vercel.app` chuyển 301 về đây) | Next.js; landing fetch phía server, 3 tab fetch trong trình duyệt |
| API công khai | Vercel project `unthreaded-api`, root repo, preset FastAPI → https://unthreaded-api.vercel.app | `src/main.py` chỉ đọc; gói = `[project].dependencies` (Vercel chạy `uv sync --no-dev` từ `uv.lock`), ~203 MiB / 500 MB — `tests/test_api_bundle.py` |
| Bản sao DB | Vercel Blob `unthreaded-db` (Private, Paris `cdg1`), pathname `threads.db` | Laptop ghi sau mỗi job; API tải về thư mục tạm, mở `mode=ro` (`src/db/published.py`) |
| Job | Laptop (Task Scheduler, ADR-0013/0017) | Snapshot 4h + NLP 12:30; bước cuối `publish_after_job()`; `job_health` có dòng "published copy" |

Code deploy tự động: mỗi commit vào `main` → Vercel build lại cả 2 project (Git integration). Số liệu đi đường riêng
(publish từ laptop) → trang công khai mới bằng lần publish gần nhất; laptop ngủ/tắt → số đứng yên (rủi ro chấp nhận,
ADR-0025). Landing ghi mốc "Data as of …" (`UI-0025-published-snapshot`).

**Biến môi trường**

| Nơi | Biến | Ghi chú |
|---|---|---|
| Laptop `.env` (thư mục chính) | `DB_BLOB_PATH=threads.db`, `BLOB_READ_WRITE_TOKEN` | Thiếu → publish bỏ qua. Chỉ đọc từ `.env` của chính checkout; worktree không bao giờ publish |
| Vercel `unthreaded-api` | `DB_BLOB_PATH`, `CORS_ALLOW_ORIGINS` (Config, các origin trang công khai, phân cách dấu phẩy) | `VERCEL=1` do Vercel tự đặt (cổng bật chế độ Blob) |
| Vercel `unthreaded-api` (do "Connect store" tạo, prefix `BLOB`) | `BLOB_STORE_ID`, `BLOB_READ_WRITE_TOKEN`, `BLOB_WEBHOOK_PUBLIC_KEY` | API đọc bằng token OIDC trong header request (đã kiểm log: "credential from header"); token RW chỉ là dự phòng. **Không "Revoke Token"** — laptop dùng nó để publish |
| Vercel `unthreaded` | `NEXT_PUBLIC_API_BASE_URL=https://unthreaded-api.vercel.app` | Gắn vào bản build → đổi phải redeploy |

Thêm tên miền cho trang (VD tên miền riêng) → thêm origin đó vào `CORS_ALLOW_ORIGINS` của API rồi redeploy API, nếu
không 3 tab trống (landing vẫn chạy vì fetch phía server).

**Lệch so với ADR-0025 (Thy chọn ghi ở đây, không ADR mới):**
1. ADR viết API lấy bản sao "khi khởi động"; code lấy ở **request đầu tiên** — trên Vercel token OIDC chỉ có trong
   header `x-vercel-oidc-token` của request, lúc khởi động chưa có credential. Quyết định gốc (Blob riêng tư → thư mục
   tạm → chỉ đọc) không đổi (Thy, 2026-10-20).
2. ADR viết deploy thử preview, Thy duyệt rồi mới public; Thy chọn **công khai ngay, không che deployment nào**
   (2026-10-28). Việc trước khi chia sẻ link rộng (bio, link CTA, rate limit `/analytics/window`, theo dõi Usage) làm
   sau trên bản đang chạy.

## Nguyên tắc kiến trúc (chi tiết + lý do trong ADR / legacy-log)

- **Batch tách khỏi serving**: pipeline ML ghi kết quả vào SQLite; FastAPI chỉ đọc.
- **Metric không gộp**: 6 index riêng + contextual score; mọi hằng số chưa calibrate ghi rõ là hypothesis.
- **Narrative Layering**: số thô → rate → median/IQR → percentile kênh → kiểm định + effect size + CI → diễn giải (`data-model.md`).
- **Claude không làm NLP core**: không classify, không embed — chỉ đặt tên cluster đã có.
- **Output hướng ra ngoài tiếng Anh**; docs/code comment tiếng Việt.
- **Bằng chứng thực nghiệm thắng lý thuyết ban đầu** (VD HDBSCAN trên UMAP space, `data-model.md` methodology log).
