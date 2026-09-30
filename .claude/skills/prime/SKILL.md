---
name: prime
description: Load just enough project context for one specific task at the start of work.
argument-hint: "<task, e.g. 'D0 reply_role' or 'fix nlp cron lock'>"
disable-model-invocation: true
---

# /prime — nạp context tối thiểu cho 1 task

Task: **$ARGUMENTS**

## Trạng thái repo

!`git status -sb`

!`git log --oneline -5`

## Trạng thái dự án

!`cat docs/status.md`

## Việc cần làm

1. Xác định task thuộc phase nào trong `docs/roadmap.md` — chỉ đọc **đúng section** đó, không đọc cả file.
2. Chọn tối đa 3 nguồn cần đọc thêm, theo bảng "Bản đồ tài liệu" trong `CLAUDE.md` (VD task NLP → section tương ứng của `docs/claude/data-model.md`; task có quyết định cũ → ADR liên quan). Rule theo mảng code (`.claude/rules/`) sẽ tự nạp khi mở file code — không cần đọc trước.
3. Dùng Grep/Glob để định vị file code liên quan; đọc hàm cần thiết, không đọc cả module lớn.
4. Trả về brief ≤ 10 dòng cho Thy (chú thích thuật ngữ bằng tiếng Việt):
   - Mục tiêu task + điều kiện "xong"
   - File sẽ chạm
   - Ràng buộc/quy tắc áp dụng (rule, ADR)
   - Bước đầu tiên đề xuất + rủi ro chính
5. Hỏi Thy xác nhận trước khi sửa code nếu task có nhiều hướng làm hợp lý.
