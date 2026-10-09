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
│   ├── agents/                # code-reviewer, qa-tester, researcher, consistency-auditor
│   └── skills/                # /prime /checkpoint /record-decision /decision-sweep /new-rq /recluster /wt /git-flow ui-lookup
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
│   ├── analysis/              # 6 index (share_rate…) + reach (tầng, ADR-0012) + stats/significance/reply_thread/topic_affinity
│   ├── db/schema.py           # SQLite: posts, content_units, insights_snapshots, account_daily_views, topics, post_topic_labels, embeddings, cluster_runs, topic_label_history
│   ├── pipeline/              # ingest, snapshot, daily_views, scheduled_job + nlp_cluster_job (cron, pythonw — ADR-0013), job_log, cầu nối clustering Win↔WSL2 (bỏ ở Phase C)
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
| Thống kê | median/IQR, Brunner-Munzel hoán vị + Cliff's δ kèm CI + Holm (numpy/scipy, ADR-0023) — engine live, so sánh theo topic trên dashboard: next | Live |
| Dashboard | Next.js 16 + Tailwind v4 + chart SVG tự dựng + Plotly (bản đồ topic) + Phosphor icons | Live (chưa deploy cố định) |
| Knowledge base | SQLite FTS5 (BM25) + dense numpy + RRF + `bge-reranker-v2-m3` | Roadmap E |
| Supervised classifier | bậc thang baseline → SVM-RBF (RQ-08) | Roadmap D |
| Chất lượng code | ruff, mypy strict, pytest; pre-commit chặn: ruff, mypy, sổ luật nhất quán (toàn repo, `--commit`), cổng review tầng 2 (chỉ commit của Claude, ADR-0015), pytest nhanh, eslint+tsc, commit-msg | Live |
| CI | GitHub Actions (`.github/workflows/ci.yml`: job py + web, ADR-0014) | Live — chạy lần đầu 2026-10-05 (PR #1: `web` đỏ vì `LayoutProps` → `67c3bf8` → xanh); chỉ chạy khi mở/cập nhật PR, push vào `main` hoặc chạy tay (Roadmap G, ADR-0019) |

## Luồng dữ liệu

```
Threads Graph API ──(Task Scheduler, 4h, pythonw)──► src/pipeline/scheduled_job
        │   posts + replies + per-post insights + account daily views
        ▼
SQLite data/threads.db ◄──(hằng ngày 12:30: src/pipeline/nlp_cluster_job)── export → WSL2 embed+cluster → import+Claude label
        │
        ▼
FastAPI src/main.py  ──►  Next.js dashboard (landing + 3 tab)

Đã có (ADR-0004): reply_role + embeddings lưu trong SQLite + hồ sơ cụm (cluster_runs). Roadmap: toàn bộ Python chạy trong WSL2 (C) → knowledge base + /kb/search (E)
```

## Nguyên tắc kiến trúc (chi tiết + lý do trong ADR / legacy-log)

- **Batch tách khỏi serving**: pipeline ML ghi kết quả vào SQLite; FastAPI chỉ đọc.
- **Metric không gộp**: 6 index riêng + contextual score; mọi hằng số chưa calibrate ghi rõ là hypothesis.
- **Narrative Layering**: số thô → rate → median/IQR → percentile kênh → kiểm định + effect size + CI → diễn giải (`data-model.md`).
- **Claude không làm NLP core**: không classify, không embed — chỉ đặt tên cluster đã có.
- **Output hướng ra ngoài tiếng Anh**; docs/code comment tiếng Việt.
- **Bằng chứng thực nghiệm thắng lý thuyết ban đầu** (VD HDBSCAN trên UMAP space, `data-model.md` methodology log).
