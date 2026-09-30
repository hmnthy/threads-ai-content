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
| [0008](0008-decision-consistency-enforcement.md) | Cưỡng chế nhất quán quyết định ↔ repo: sổ luật + check.py + consistency-auditor + /decision-sweep, pre-commit chặn | Accepted | 2026-09-30 |

Dự kiến (đánh số giữ chỗ theo `docs/roadmap.md`): 0002 runtime WSL2 · 0004 định nghĩa `full_text` / `reply_role` · 0005 experiment tracking JSON + git · 0006 lưu trữ + truy xuất KB · 0007 dữ liệu bình luận follower & privacy.
