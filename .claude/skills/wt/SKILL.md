---
name: wt
description: Git worktree workflow for threads-ai-content — create, work in, and clean up an isolated worktree safely (env, database, Windows long-path caveats).
argument-hint: "new <branch> | list | clean <branch>"
disable-model-invocation: true
---

# /wt — quản lý git worktree

Lệnh: **$ARGUMENTS**

!`git worktree list`

## new <branch>

- Ưu tiên công cụ worktree của Claude Code (thư mục `.claude/worktrees/`, đã gitignore; `.worktreeinclude` tự copy `.env`). Hoặc thủ công: `git worktree add .claude/worktrees/<branch> -b <branch>`.
- **Database** (trước Phase C): `DEFAULT_DB_PATH` là đường dẫn tương đối → worktree **không có** `data/threads.db` (hoặc có bản cũ). Chỉ chạy pipeline/API/cron từ checkout chính. Cần data trong worktree để thử nghiệm → copy DB sang worktree và coi là **bản nháp**, không bao giờ copy ngược lại. Sau Phase C: `db_path()` tự dùng DB của checkout chính; thử nghiệm đổi schema thì đặt `THREADS_DB_PATH` trỏ tới bản copy.
- Dashboard trong worktree cần `npm install` riêng (node_modules không chia sẻ).

## list

`git worktree list` + với mỗi worktree: branch, số commit chưa merge vào `main` (`git log main..<branch> --oneline`), có thay đổi chưa commit không (`git -C <path> status --short`).

## clean <branch>

1. Kiểm tra trước khi xoá: thay đổi chưa commit → lưu patch (`git -C <path> diff > <scratchpad>/<branch>.patch`) và báo Thy; commit chưa merge → hỏi Thy.
2. `git worktree remove <path>` → `git branch -d <branch>` (chỉ `-D` khi Thy đồng ý bỏ commit) → `git worktree prune`.
3. **Windows**: worktree có `node_modules` hay lỗi "Filename too long" khi xoá — git sẽ gỡ đăng ký nhưng để lại thư mục. Xoá phần còn lại bằng PowerShell: `Remove-Item -LiteralPath "\\?\<đường dẫn tuyệt đối>" -Recurse -Force`.
4. Xác nhận `git worktree list` chỉ còn những worktree đang dùng.

## Review tầng 2 trong worktree (ADR-0015)

Dấu review chỉ ghi cho worktree của **phiên** (cwd của hook). Muốn commit trong 1 worktree → mở phiên Claude Code ở worktree đó (hoặc dùng công cụ worktree của Claude Code) rồi chạy `@agent-code-reviewer` — không `cd` tay sang worktree từ phiên ở checkout chính.
