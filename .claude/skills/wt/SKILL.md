---
name: wt
description: Git worktree workflow for threads-ai-content — create, work in, and clean up an isolated worktree safely (env, database, Windows long-path caveats).
argument-hint: "new <branch> | list | clean <branch>"
disable-model-invocation: true
---

# /wt — quản lý git worktree

Quy trình chung (khi nào tách nhánh/worktree, PR, merge): ADR-0019, `docs/claude/git-workflow.md`, skill `/git-flow`. Skill này lo phần cơ học: tạo, liệt kê, dọn.

Lệnh: **$ARGUMENTS**

!`git worktree list`

## new <branch>

- Ưu tiên công cụ worktree của Claude Code (thư mục `.claude/worktrees/`, đã gitignore; `.worktreeinclude` tự copy `.env`) — công cụ tạo mới luôn tách từ `origin/main`. Gốc khác (nhánh xếp chồng) → thủ công `git -C <thư mục chính> worktree add --no-track -b <branch> .claude/worktrees/<tên> <gốc>` rồi vào bằng công cụ worktree với `path`; copy `.env` tay.
- **Database** (trước Phase C): `DEFAULT_DB_PATH` là đường dẫn tương đối → worktree **không có** `data/threads.db` (hoặc có bản cũ). Chỉ chạy pipeline/API/cron từ checkout chính. Cần data trong worktree để thử nghiệm → copy DB sang worktree và coi là **bản nháp**, không bao giờ copy ngược lại. Sau Phase C: `db_path()` tự dùng DB của checkout chính; thử nghiệm đổi schema thì đặt `THREADS_DB_PATH` trỏ tới bản copy.
- Dashboard trong worktree cần `npm install` riêng (node_modules không chia sẻ).

## list

`git worktree list` + với mỗi worktree: branch, số commit chưa merge vào `main` trên GitHub (`git fetch origin` rồi `git log origin/main..<branch> --oneline`), có thay đổi chưa commit không (`git -C <path> status --short`).

## clean <branch>

1. Kiểm tra trước khi xoá: thay đổi chưa commit → lưu patch (`git -C <path> add -N .` rồi `git -C <path> diff HEAD --binary --output=<scratchpad>/<branch>.patch` — không dùng `>`: PowerShell 5.1 ghi UTF-16) và báo Thy.
2. `git fetch --prune` → nhánh phải nằm trong `git branch --merged origin/main` (`git branch -d` chỉ so với upstream của nhánh hoặc HEAD — nhánh đã push mà PR đóng không merge vẫn xoá được). Không có trong danh sách → hỏi Thy.
3. `git worktree remove <path>` → `git branch -d <branch>` (chỉ `-D` khi Thy đồng ý bỏ commit) → `git worktree prune`.
4. **Windows**: worktree có `node_modules` hay lỗi "Filename too long" khi xoá — git sẽ gỡ đăng ký nhưng để lại thư mục. Xoá phần còn lại bằng PowerShell: `Remove-Item -LiteralPath "\\?\<đường dẫn tuyệt đối>" -Recurse -Force`.
5. Xác nhận `git worktree list` chỉ còn những worktree đang dùng.

## Review tầng 2 trong worktree (ADR-0015)

Dấu review chỉ ghi cho worktree của **phiên** (cwd của hook). Muốn commit trong 1 worktree → mở phiên Claude Code ở worktree đó (hoặc dùng công cụ worktree của Claude Code) rồi chạy `@agent-code-reviewer` — không `cd` tay sang worktree từ phiên ở checkout chính.
