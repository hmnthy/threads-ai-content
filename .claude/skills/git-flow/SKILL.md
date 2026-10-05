---
name: git-flow
description: Git workflow guide for threads-ai-content (ADR-0019) — where am I, start a task on a branch + worktree, finish it via PR/CI/merge commit. Use when starting any change, before committing on a branch, when the session-start hook prints a "Git:" warning, or when Thy asks about branches/worktrees/PRs.
argument-hint: "status | start <việc> | finish"
---

# /git-flow — quy trình git (ADR-0019, `docs/claude/git-workflow.md`)

Lệnh: **$ARGUMENTS** (trống = `status`)

!`git worktree list`

Ba quy tắc: **thư mục chính luôn ở `main`** (2 cron chạy code ở đó, kể cả file chưa commit) · **không commit thẳng lên `main`** — nhánh → PR → CI → merge · **merge kiểu "Create a merge commit"**. Giải thích cho Thy bằng lời thường, chú thích thuật ngữ lần đầu. `<CHÍNH>` = thư mục chính (mục đầu tiên của `git worktree list`).

## status

1. `uv run python -m scripts.git_hygiene` (cùng cảnh báo hook đầu phiên in).
2. Bảng cho Thy: thư mục nào · nhánh nào · commit chưa vào `origin/main` (`git log --oneline origin/main..<nhánh>`) · việc dở chưa commit (`git -C <path> status --short`) · đã push chưa (`git branch -vv`: không có `[origin/…]` = chưa push lần nào; `ahead N` = N commit chưa push).
3. Kết luận 1 dòng: việc nên làm tiếp (VD "mở PR cho `feat/x`", "PR đã merge → bước 8: pull + `uv sync --frozen` ở thư mục chính").

## start <việc>

1. Kiểm tra trước: thư mục chính có thay đổi chưa commit ở code cron (`uv run python -m scripts.git_hygiene` in WARN) → báo Thy, chuyển sang worktree bằng patch (doc mục 5 — `--output` + đường dẫn tuyệt đối, không dùng `>`), không commit ở thư mục chính.
2. Chọn tên nhánh theo loại: `feat/` · `fix/` · `chore/` · `docs/` · `exp/` + mô tả ngắn kebab-case. Đọc tên cho Thy duyệt nếu việc chưa rõ.
3. Gốc nhánh: `origin/main` sau `git fetch origin`. Ngoại lệ — việc cần code của 1 nhánh chưa merge → tách từ nhánh đó (nhánh xếp chồng) và nói rõ cho Thy rằng PR này mở sau khi nhánh kia merge.
4. Tạo: `git -C <CHÍNH> worktree add --no-track -b <nhánh> .claude/worktrees/<tên> <gốc>` (luôn `-C <CHÍNH>` để không tạo worktree lồng trong worktree hiện tại; `--no-track` để nhánh chưa push không hiện `[origin/main: ahead N]` như thể đã push) → vào worktree bằng công cụ worktree của Claude Code (`EnterWorktree` với `path`) để hook review tầng 2 ghi dấu đúng chỗ (ADR-0015).
5. Chuẩn bị: copy `<CHÍNH>\.env` sang worktree; `uv sync --frozen`; dashboard → `npm install` trong `src/dashboard`; cần data → copy `data/threads.db` (bản nháp, không copy ngược — xem `/wt`).

## finish

Checklist — dừng ở bước nào chưa đạt và nói rõ cho Thy:
1. Việc của nhánh đã xong, `/checkpoint` cuối đã commit; `git status` sạch trong worktree.
2. `main` trên GitHub có commit mới? `git fetch origin` → `git merge origin/main` trong worktree, sửa xung đột, chạy lại test.
3. Full `uv run pytest -q`, ruff, mypy, `check --all` xanh (dashboard: `npm run lint` + `npm run typecheck` + `npm run build`).
4. Thy push: `git push -u origin <nhánh>` (lệnh push của Claude bị chặn — chỉ đưa lệnh).
5. Thy mở PR: `https://github.com/hmnthy/threads-ai-content/compare/main...<nhánh>`; tiêu đề = tóm tắt đợt việc (tiếng Anh), mô tả liệt kê ADR/commit chính.
6. CI (tab *Checks*: job `py` + `web`) xanh. Đỏ → đọc log, sửa trên cùng nhánh, Thy push lại.
7. Thy bấm **Create a merge commit** → *Delete branch* trên GitHub.
8. Ở thư mục chính: `git checkout main` (nếu chưa) → `git pull` → **luôn** `uv sync --frozen` (cron chạy thẳng `.venv`, không tự sync; chạy khi `job_health` không báo "task running now") → `uv run python -m scripts.git_hygiene` không còn WARN.
9. `/wt clean <nhánh>` (kiểm `git branch --merged origin/main` sau `git fetch --prune` trước khi xoá); cập nhật `docs/status.md` nếu đợt việc đổi trạng thái dự án.
