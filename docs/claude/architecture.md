# Architecture — threads-ai-content

> Đọc khi: cần cấu trúc thư mục, tech stack, hoặc luồng dữ liệu tổng thể.
> Lý do của từng lựa chọn: `docs/decisions/` (ADR) + `docs/decisions/legacy-log.md` (trước 2026-09-30). Kế hoạch: `docs/roadmap.md`.

## Cấu trúc thư mục

```
threads-ai-content/
├── CLAUDE.md                  # ≤80 dòng: mission, quy tắc tuyệt đối, bản đồ tài liệu
├── .claude/
│   ├── settings.json          # hooks, attribution tắt, deny .env
│   ├── hooks/                 # session_status / guard_commit / ruff_on_edit / notify+toast
│   ├── rules/                 # quy tắc theo đường dẫn (paths:) — chỉ nạp khi chạm đúng mảng code
│   ├── agents/                # code-reviewer, qa-tester, researcher
│   └── skills/                # /prime /checkpoint /record-decision /new-rq /recluster /wt ui-lookup
├── .mcp.json                  # context7 + huggingface
├── docs/
│   ├── status.md              # trạng thái hiện tại (≤60 dòng)
│   ├── roadmap.md             # phase C → F + cổng chatbot
│   ├── decisions/             # ADR 1 file/quyết định + legacy-log.md
│   ├── claude/                # tài liệu tham chiếu: architecture, data-model, design-system, dev-rules
│   ├── rq/                    # (sắp có) câu hỏi nghiên cứu RQ-xx
│   ├── research/              # PRIVATE, gitignored — market scan, methodology
│   ├── archive/               # plan/sprint cũ, giữ nguyên văn
│   ├── design/ · screenshots/
├── src/
│   ├── api/                   # Threads Graph API client (httpx async, pydantic, cache TTL 6h, pagination)
│   ├── models/                # ContentUnit, InsightSnapshot
│   ├── processing/            # thread_reconstruction (root + continuation), text (NFC, dấu thanh)
│   ├── nlp/                   # language (CMI + LID cấp từ), embeddings (bge-m3), topics (UMAP+HDBSCAN+Claude label)
│   ├── analysis/              # 6 index + stats/significance/reply_thread/topic_affinity
│   ├── db/schema.py           # SQLite: posts, content_units, insights_snapshots, account_daily_views, topics, post_topic_labels
│   ├── pipeline/              # ingest, snapshot, daily_views, scheduled_job, cầu nối clustering Win↔WSL2 (bỏ ở Phase C)
│   ├── main.py                # FastAPI — chỉ đọc SQLite, không load model trong request
│   └── dashboard/             # Next.js 16 + Tailwind v4: landing `/` + `/overview` `/analytics` `/topics`
├── tools/ui-ux-pro-max/       # CLI tra cứu UI (vendored) — gọi qua skill ui-lookup
├── tests/                     # pytest (183 test), respx mock HTTP
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
| Topic discovery | UMAP (3D) + HDBSCAN (`leaf`, `min_cluster_size=4`, `n_neighbors=10`) | Live, re-cluster hằng ngày |
| LLM | Claude API `claude-opus-5` — CHỈ đặt tên cluster (tiếng Anh) | Live |
| Thống kê | median/IQR, Mann-Whitney U + Cliff's δ + bootstrap CI (scipy) | Live |
| Dashboard | Next.js 16 + Tailwind v4 + Recharts + Phosphor icons | Live (chưa deploy cố định) |
| Knowledge base | SQLite FTS5 (BM25) + dense numpy + RRF + `bge-reranker-v2-m3` | Roadmap E |
| Supervised classifier | bậc thang baseline → SVM-RBF (RQ-08) | Roadmap D |
| Chất lượng code | ruff, mypy strict, pytest, pre-commit (+ commit-msg guard) | Live |
| CI | GitHub Actions | Roadmap G |

## Luồng dữ liệu

```
Threads Graph API ──(Task Scheduler, 4h: run_snapshot_job.bat)──► src/pipeline/scheduled_job
        │   posts + replies + per-post insights + account daily views
        ▼
SQLite data/threads.db ◄──(hằng ngày 3h: run_nlp_cluster_job.bat)── export → WSL2 embed+cluster → import+Claude label
        │
        ▼
FastAPI src/main.py  ──►  Next.js dashboard (landing + 3 tab)

Roadmap: toàn bộ Python chạy trong WSL2 (C) → reply_role + embeddings persist (D0) → knowledge base + /kb/search (E)
```

## Nguyên tắc kiến trúc (chi tiết + lý do trong ADR / legacy-log)

- **Batch tách khỏi serving**: pipeline ML ghi kết quả vào SQLite; FastAPI chỉ đọc.
- **Metric không gộp**: 6 index riêng + contextual score; mọi hằng số chưa calibrate ghi rõ là hypothesis.
- **Narrative Layering**: số thô → rate → median/IQR → percentile kênh → kiểm định + effect size + CI → diễn giải (`data-model.md`).
- **Claude không làm NLP core**: không classify, không embed — chỉ đặt tên cluster đã có.
- **Output hướng ra ngoài tiếng Anh**; docs/code comment tiếng Việt.
- **Bằng chứng thực nghiệm thắng lý thuyết ban đầu** (VD HDBSCAN trên UMAP space, `data-model.md` methodology log).
