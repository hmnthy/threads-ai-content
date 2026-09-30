# Unthreaded (repo `threads-ai-content`)

Dự án NLP trên data thật của kênh Threads **@thydilammuon** (người Việt tại Pháp: alternance, xin việc, đời sống).
Scope (ADR-0001): **phân tích NLP sâu → knowledge base (cơ sở tri thức) cập nhật liên tục → chỉ sau cổng chất lượng: chatbot + landing thương hiệu.**
<!-- consistency: allow ADR0001-generation ADR0001-carousel ADR0001-kol -->
Không generation giọng văn, không carousel, không KOL engine. Portfolio NLP/MLE — repo private, sẽ curate sang repo public riêng.

## Quy tắc tuyệt đối

- Không đăng gì lên Threads. Không commit `.env`, token, data cá nhân (`content/`, `data/`, `docs/research/`).
- Commit message **tiếng Anh**, **không** trailer `Co-Authored-By` (hook + `attribution` đã cưỡng chế — đừng tìm cách vượt).
- Product copy (dashboard, README, label do LLM sinh) **tiếng Anh**; docs + code comment **tiếng Việt**.
- Khi trao đổi với Thy: **chú thích thuật ngữ chuyên môn bằng tiếng Việt** ở lần đầu xuất hiện.
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
`ThreadsAI_SnapshotJob_4h`, `ThreadsAI_NLPClusterJob_Daily` (xem log `data/logs/`).

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
- **Git**: không làm trực tiếp trên `main` cho việc nhiều bước — branch hoặc worktree (`/wt`). Mọi worktree dùng chung DB
  của checkout chính (sau Phase C); trước đó `data/` của worktree là bản riêng, có thể cũ.
- **Subagents**: `@agent-code-reviewer` trước commit có logic/thống kê · `@agent-qa-tester` viết/chạy test (chỉ sửa `tests/`) ·
  `@agent-researcher` tìm paper/model/docs có trích nguồn (web + MCP `huggingface`, `context7`) ·
  `@agent-consistency-auditor` kiểm toán độc lập 1 ADR (dùng trong `/decision-sweep`).
- **Cổng pre-commit** (chặn commit): ruff, mypy, sổ luật nhất quán, pytest nhanh, eslint + tsc khi chạm dashboard, commit-msg.
  Hook đầu phiên báo số vi phạm ≠ 0 → chạy `/decision-sweep` trước việc mới.
- **Phiên mới**: đọc status do hook in ra; cần thêm context cho 1 task → `/prime <task>`.
- Thy dùng song song Claude Design/Cowork trên cùng repo → `git status` trước khi sửa; thấy thay đổi lạ thì hỏi, không ghi đè.
