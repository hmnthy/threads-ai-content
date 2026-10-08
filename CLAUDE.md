# Unthreaded (repo `threads-ai-content`)

Dự án NLP trên data thật của kênh Threads **@thydilammuon** (người Việt tại Pháp: alternance, xin việc, đời sống).
Scope (ADR-0001): **phân tích NLP sâu → knowledge base (cơ sở tri thức) cập nhật liên tục → chỉ sau cổng chất lượng: chatbot + landing thương hiệu.**
<!-- consistency: allow ADR0001-generation ADR0001-carousel ADR0001-kol -->
Không generation giọng văn, không carousel, không KOL engine. Portfolio NLP/MLE — repo private, sẽ curate sang repo public riêng.

## Quy tắc tuyệt đối

- Không đăng gì lên Threads. Không commit `.env`, token, data cá nhân (`content/`, `data/`, `docs/research/`).
- Commit message **tiếng Anh**, **không** trailer `Co-Authored-By` (hook + `attribution` đã cưỡng chế — đừng tìm cách vượt).
- Product copy (dashboard, README, label do LLM sinh) **tiếng Anh**; docs + code comment **tiếng Việt**.
- Khi trao đổi với Thy: **mọi thuật ngữ kỹ thuật phải có ngoặc giải thích** ở lần đầu xuất hiện **trong mỗi câu trả lời**
  (cả câu hỏi lựa chọn, plan, báo cáo) — VD `PR (Pull Request — "đề nghị gộp nhánh")`; không được bỏ qua.
- Không hằng số heuristic chưa gắn nhãn; mọi kết luận thống kê kèm n, effect size, CI (`docs/claude/data-model.md` — Narrative Layering).
- Đề xuất trong `docs/research/` (private) chỉ được triển khai sau khi Thy duyệt → ghi ADR.
- Bằng chứng từ data thật > giả định; "verify live" trước khi tin shape của Threads API.
- Mockup chỉ quyết định design, không bao giờ quyết định methodology.

## Lệnh

```bash
uv sync                                    # cài deps (Python 3.12)
uv run pytest -q                           # cả suite ~1 phút (pre-commit chạy bộ nhanh ~20s)
uv run pre-commit install                  # 1 lần sau khi clone: bật các cổng chặn commit
uv run ruff check . && uv run ruff format . && uv run mypy
uv run uvicorn src.main:app --reload --port 8000
cd src/dashboard && npm run dev            # http://localhost:3000 (cần backend chạy)
```

ML (embedding/UMAP/HDBSCAN) **chỉ chạy trong WSL2** — Smart App Control chặn DLL trên Windows. Cron: Task Scheduler
`ThreadsAI_SnapshotJob_4h`, `ThreadsAI_NLPClusterJob_Daily` (sức khoẻ: `python -m scripts.job_health`; log `data/logs/`).

## Bản đồ tài liệu

| Cần gì | Ở đâu |
|---|---|
| Đang ở đâu, làm gì tiếp | `docs/status.md` (hook SessionStart tự tóm tắt) |
| Kế hoạch theo phase + cổng chatbot | `docs/roadmap.md` |
| Vì sao quyết định X | `docs/decisions/` (ADR) · trước 2026-09-30: `docs/decisions/legacy-log.md` |
| Cấu trúc thư mục, tech stack, luồng dữ liệu | `docs/claude/architecture.md` |
| Threads API field/metric, công thức index, NLP pipeline, methodology log | `docs/claude/data-model.md` |
| Design UI (bắt buộc trước mọi việc UI) | `docs/claude/design-system.md` — rule tự nạp khi chạm `src/dashboard/` |
| Setup môi trường, phối hợp Claude Design/Cowork | `docs/claude/dev-rules.md` |
| Câu hỏi nghiên cứu | `docs/rq/RQ-xx.md` (tạo bằng `/new-rq`) |

Quy tắc theo mảng code nằm ở `.claude/rules/` và **tự nạp** khi đọc file khớp đường dẫn — không cần đọc trước.

## Cách làm việc

- **Checkpoint**: sau mỗi bước có test/build xanh → đề xuất `/checkpoint` (chạy kiểm tra, soạn commit, **chờ Thy đồng ý**, cập nhật `docs/status.md`).
- **Quyết định mới** (kiến trúc, methodology, metric) → `/record-decision` (kèm luật trong `docs/decisions/invariants.toml`)
  → `/decision-sweep` lan ra toàn repo. Pre-commit **chặn** commit vi phạm sổ luật; ngoại lệ có chủ đích ghi `consistency: allow <id>`.
- **Git** (ADR-0019, `docs/claude/git-workflow.md`, `/git-flow`): thư mục chính **luôn ở `main`** (cron chạy code ở đó, kể cả
  file chưa commit) — mọi thay đổi làm trên nhánh mới trong worktree → PR → CI xanh → merge commit. Trước Phase C,
  `data/` của worktree là bản riêng, có thể cũ. Hook đầu phiên in `Git:` khi lệch quy ước.
- **Subagents**: `@agent-code-reviewer` **bắt buộc** trước commit chạm logic (git hook pre-commit chặn nếu thiếu, ADR-0015) · `@agent-qa-tester` viết/chạy test (chỉ sửa `tests/`) ·
  `@agent-researcher` tìm paper/model/docs có trích nguồn (web + MCP `huggingface`, `context7`) ·
  `@agent-copy-reviewer` đọc chữ tiếng Anh hiển thị như tech lead NLP + người đọc mới, đề xuất câu viết lại (Thy duyệt câu cuối) ·
  `@agent-consistency-auditor` kiểm toán độc lập 1 ADR (dùng trong `/decision-sweep`; **bắt buộc** trước commit ADR — git hook pre-commit chặn, ADR-0015).
- **Cổng pre-commit** (chặn commit): ruff, mypy, sổ luật nhất quán (quét TOÀN repo, ~6s), pytest nhanh, eslint + tsc khi chạm dashboard, cổng review tầng 2 (chỉ commit của Claude), commit-msg.
  CI (`.github/workflows/ci.yml`) chạy lại các cổng trên máy sạch khi mở PR hoặc push vào `main`.
  Hook đầu phiên báo số vi phạm ≠ 0 → chạy `/decision-sweep` trước việc mới.
- **Phiên mới**: đọc status do hook in ra; cần thêm context cho 1 task → `/prime <task>`.
- Thy dùng song song Claude Design/Cowork trên cùng repo → `git status` trước khi sửa; thấy thay đổi lạ thì hỏi, không ghi đè.
