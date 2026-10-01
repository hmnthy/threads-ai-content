# Decisions (ADR)

Mỗi quyết định kiến trúc/methodology = 1 file ngắn `NNNN-ten-ngan.md`, theo `0000-template.md`. Tạo bằng skill `/record-decision`.

**Quy tắc**
- Không sửa ADR đã `Accepted` để đổi ý — viết ADR mới và đổi trạng thái ADR cũ thành `Superseded by ADR-XXXX`.
- Đề xuất từ `docs/research/` (private) chỉ thành ADR khi Thy đã duyệt.
- Bảng quyết định trước 2026-09-30: `legacy-log.md` (lưu trữ nguyên văn, không sửa).

| # | Quyết định | Trạng thái | Ngày |
|---|---|---|---|
| [0001](0001-less-is-more-scope.md) | Thu hẹp scope: bỏ generation giọng văn, carousel, KOL engine; tập trung NLP → knowledge base | Accepted | 2026-09-30 |
| [0003](0003-docs-and-harness-structure.md) | Cấu trúc tài liệu + harness Claude Code: CLAUDE.md ngắn, rules theo đường dẫn, ADR, skills, subagents | Accepted | 2026-09-30 |
| [0004](0004-reply-roles-and-clean-full-text.md) | Phân vai reply (self_continuation / author_answer / outbound), `full_text` sạch, lưu embedding + hồ sơ cụm, bỏ `'fixed'` | Accepted | 2026-10-01 |
| [0008](0008-decision-consistency-enforcement.md) | Cưỡng chế nhất quán quyết định ↔ repo: sổ luật + check.py + consistency-auditor + /decision-sweep, pre-commit chặn | Accepted | 2026-09-30 |
| [0009](0009-product-name-unthreaded.md) | Tên hiển thị sản phẩm "Unthreaded" (slug `threads-ai-content` giữ nguyên) + câu miễn trừ Meta | Accepted | 2026-09-30 |
| [0010](0010-sqlite-only-database.md) | SQLite là CSDL duy nhất (gồm cả knowledge base) — bỏ lời hứa PostgreSQL | Accepted | 2026-09-30 |
| [0011](0011-zero-view-posts-are-missing-data.md) | Bài views = 0 là dữ liệu thiếu — loại khỏi mọi phân phối rate, báo số bị loại | Accepted | 2026-09-30 |
| [0013](0013-headless-cron-jobs.md) | Cron job chạy bằng pythonw (không console), job tự ghi log UTF-8, hook đo độ tươi từ DB | Accepted | 2026-10-01 |
| [0014](0014-whole-repo-gates-and-ci.md) | Pre-commit quét toàn repo (`--commit`), `--all` quét cả file chưa track, CI GitHub Actions | Accepted | 2026-10-01 |

Dự kiến (đánh số giữ chỗ theo `docs/roadmap.md` và plan P1 dashboard): 0002 runtime WSL2 · 0005 experiment tracking JSON + git · 0006 lưu trữ + truy xuất KB · 0007 dữ liệu bình luận follower & privacy · 0012 nhãn viral + kiểm định biến giải thích (plan P1 Bước 2).
