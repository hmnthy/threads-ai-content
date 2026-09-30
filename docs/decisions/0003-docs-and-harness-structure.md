# ADR-0003: Cấu trúc tài liệu và harness Claude Code

- **Trạng thái**: Accepted
- **Ngày**: 2026-09-30
- **Người quyết**: Thy (yêu cầu), Claude (thiết kế)

## Bối cảnh

- `CLAUDE.md` 115 dòng/13KB, nạp mỗi phiên, bảng trạng thái cũ từ 2026-08-29; decisions log là 1 bảng ~50 dòng trong `architecture.md`; 3 file kế hoạch chồng nhau (`next-steps.md`, `project-summary.md`, `sprint-plan.md`) đều lỗi thời.
- Không có hooks, subagents, skills dự án, MCP. 7 skill design vendored (~99KB SKILL.md) có mô tả chiếm context mỗi phiên dù không dùng.
- Quy tắc "không trailer Co-Authored-By" chỉ viết bằng chữ — nhưng chính harness tự chèn yêu cầu thêm trailer.

## Quyết định

Theo khuyến nghị chính thức (code.claude.com/docs: memory, hooks, skills, sub-agents):

1. **`CLAUDE.md` ≤ 80 dòng** — chỉ mission, quy tắc tuyệt đối, lệnh chạy, bản đồ tài liệu, workflow.
2. **Quy tắc theo mảng code → `.claude/rules/*.md` có `paths:`** — chỉ nạp khi Claude đọc file khớp đường dẫn (VD rule design chỉ nạp khi chạm `src/dashboard/`).
3. **Trạng thái → `docs/status.md`** (≤ 60 dòng, chỉ hiện tại) + **kế hoạch → `docs/roadmap.md`**. Lịch sử là git log + ADR, không phải file log.
4. **Quyết định → ADR 1 file/quyết định** trong `docs/decisions/`; bảng cũ lưu nguyên văn ở `legacy-log.md`.
5. **Quy tắc bắt buộc được cưỡng chế bằng máy, không chỉ bằng chữ**: `attribution` rỗng trong `.claude/settings.json`, hook PreToolUse chặn trailer, hook git `commit-msg`, `permissions.deny` cho `.env`.
6. **Việc lặp lại → skills** (`/prime`, `/checkpoint`, `/record-decision`, `/new-rq`, `/recluster`, `/wt`, `ui-lookup`; `/kb-eval` tạo ở Phase E khi KB tồn tại), đa số `disable-model-invocation: true` để mô tả không tốn context.
7. **3 subagent** có tool giới hạn: `code-reviewer` (chỉ đọc), `qa-tester` (chỉ sửa `tests/`), `researcher` (web + MCP, chỉ đọc).
8. **Xoá 6 skill design không dùng**; `ui-ux-pro-max` chuyển sang `tools/` và chỉ gọi qua CLI.
9. **MCP tối thiểu**: `context7` (docs thư viện cập nhật), `huggingface` (model/dataset/paper).

## Phương án đã cân nhắc

| Phương án | Vì sao không chọn |
|---|---|
| Giữ `docs/claude/*.md` + trỏ từ CLAUDE.md | Vẫn phụ thuộc Claude tự nhớ đọc; rules có `paths:` tự nạp đúng lúc |
| `@import` các file docs vào CLAUDE.md | Docs chính thức: `@import` nạp toàn bộ lúc khởi động, không tiết kiệm context |
| Giữ `.claude/commands/` | Commands đã gộp vào skills; skills có frontmatter kiểm soát context tốt hơn |
| Hook chặn đọc `.env` | `permissions.deny` là cơ chế native, ít thành phần hơn |

## Hệ quả

- `docs/claude/data-model.md` và `design-system.md` giữ nguyên vai trò tài liệu tham chiếu, được rules trỏ tới.
- `docs/claude/architecture.md` rút gọn, bỏ decisions log và roadmap (đã chuyển đi).
- Hook dùng `uv run --no-sync` — phụ thuộc `uv` có trên PATH của Claude Code; đổi lệnh nếu môi trường khác.
- Xem lại khi: `/context` cho thấy memory files > ~10% context lúc khởi động, hoặc rules nạp sai thời điểm.
