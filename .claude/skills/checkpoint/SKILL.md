---
name: checkpoint
description: Propose a git checkpoint commit for threads-ai-content once a step is done and green — run the relevant checks, update docs/status.md, draft an English commit message, and wait for Thy's explicit OK before committing. Use proactively after finishing any meaningful step, and whenever the session status reports uncommitted files.
allowed-tools: Bash(git status *) Bash(git diff *) Bash(git log *) Bash(uv run ruff *) Bash(uv run mypy *) Bash(uv run pytest *)
---

# /checkpoint — commit tại điểm dừng an toàn

## 1. Xem thay đổi

- `git status --short` và `git diff --stat` (cả staged). Không có gì → báo "không có gì để commit" và dừng.
- Phân loại file: thuộc cùng 1 đơn vị việc không? Nếu lẫn 2 việc khác nhau → đề xuất tách thành 2 commit.
- **Không bao giờ** đưa vào commit: `.env*`, `data/`, `content/`, `docs/research/`, file tạm, `node_modules/`.

## 2. Kiểm tra tương xứng với thay đổi

| Thay đổi | Chạy |
|---|---|
| `src/**/*.py`, `tests/**` | `uv run ruff check .` · `uv run mypy` · `uv run pytest <phạm vi liên quan> -q` (cả suite nếu đụng `src/db`, `src/models`, `src/main.py`) |
| `src/dashboard/**` | `npm run lint` + `npm run build` trong `src/dashboard` |
| Chỉ docs/config | không cần test; kiểm link/đường dẫn nhắc tới có tồn tại |

Có fail → dừng, báo lỗi, **không** commit. Thay đổi có logic/metric/thống kê/NLP → đề xuất gọi `@agent-code-reviewer` trước.

## 3. Cập nhật `docs/status.md` (đưa vào cùng commit)

Sửa "Now"/"Next"/"Blocked" nếu đã đổi; "Last checkpoint" = subject của commit sắp tạo. Giữ ≤ 60 dòng.

## 4. Soạn commit message

- **Tiếng Anh**, subject dạng mệnh lệnh ≤ 72 ký tự, body gạch đầu dòng giải thích **vì sao** (không liệt kê lại diff).
- **Không** trailer `Co-Authored-By` hay dòng quảng cáo công cụ nào.
- Nếu có quyết định kiến trúc/methodology mới mà chưa có ADR → nhắc `/record-decision` trước.

## 5. Chờ xác nhận

Trình bày cho Thy: danh sách file, kết quả kiểm tra, commit message. **Chỉ commit khi Thy đồng ý rõ ràng** trong lượt này. Sau khi commit: báo hash; nếu nhánh đã đủ chín thì gợi ý push / merge.
