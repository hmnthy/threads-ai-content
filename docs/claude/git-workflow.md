# Quy trình git của Unthreaded (ADR-0019)

> Viết cho người mới dùng git chuyên sâu. Ngắn gọn: **thư mục chính luôn ở `main`; mọi thay đổi làm trong worktree trên nhánh riêng; xong thì PR → CI xanh → merge commit → dọn.** Hỏi nhanh bất cứ lúc nào: `/git-flow status`.

## 1. Năm khái niệm

| Khái niệm | Hình dung | Trong repo này |
|---|---|---|
| **Commit** | 1 "ảnh chụp" có tên của các file đã chọn | Mỗi ADR thường là 1 commit, message tiếng Anh |
| **Branch** (nhánh) | 1 dấu kẹp trang đánh dấu 1 dòng commit | `main` = bản chính thức; `feat/…`, `chore/…` = việc đang làm |
| **Worktree** | 1 *thư mục làm việc* bày 1 nhánh ra ổ đĩa | Thư mục chính `threads-ai-content/` + các thư mục phụ trong `.claude/worktrees/` |
| **Pull request (PR)** | Đơn xin đưa 1 nhánh vào `main` trên GitHub | CI tự chạy lại mọi cổng trên máy sạch |
| **Merge commit** | Commit "Merge PR #n" gộp nhánh vào `main`, giữ nguyên từng commit con | Lịch sử `main` vẫn thấy từng ADR |

Branch là *lịch sử*, worktree là *chỗ làm*. Nhiều worktree dùng chung 1 lịch sử (`.git`): commit ở thư mục nào thì thư mục kia thấy ngay — nhưng file đang mở, file chưa commit, `.env`, `.venv`, `node_modules`, `data/` là của riêng từng thư mục. `origin/main` là bản `main` trên GitHub *theo lần `git fetch` gần nhất*; `main` (không có `origin/`) là bản trên máy — chỉ đổi khi `git pull` ở thư mục chính.

## 2. Ba quy tắc bất biến

1. **Thư mục chính luôn ở `main`.** 2 cron (snapshot mỗi 4h lúc xx:15, NLP 12:30 — ADR-0013/0017) chạy code đang nằm trong thư mục này, *kể cả file chưa commit*, bằng `.venv` của nó (không tự `uv sync`), và mỗi lần chạy đều migrate DB thật (`create_schema()`). Vì vậy thư mục chính chỉ dùng để: cron chạy, xem dashboard/API trên data thật, `git pull` + `uv sync` sau khi merge. Không sửa code ở đây.
   - Bài học 2026-10-04: đang sửa ADR-0018 trong thư mục chính → job snapshot 21:15 chạy bản nháp và migrate DB thật trước khi Thy duyệt.
2. **Không commit thẳng lên `main`.** Mọi thay đổi đi qua nhánh → PR → CI xanh → merge commit. `main` = bản đã qua cổng trên máy sạch.
3. **Merge kiểu "Create a merge commit"** (không squash, không rebase) — giữ từng commit ADR trong lịch sử `main` và các mã commit (VD `f908d8a`) mà docs/memory nhắc tới vẫn còn đúng.

## 3. Cây quyết định — bắt đầu 1 việc

```
Có sửa file nào trong repo không?
├─ Không (chỉ đọc, chạy thử, xem dashboard) → làm ở thư mục chính, không cần nhánh
└─ Có → tạo NHÁNH MỚI từ origin/main  +  WORKTREE riêng cho nhánh đó   (/git-flow start <việc>)
        Đặt tên nhánh theo loại việc:
        feat/…   tính năng, bước của plan (feat/reach-tiers)
        fix/…    sửa lỗi (fix/job-health-morning-warn)
        chore/…  hạ tầng, hook, quy trình (chore/git-workflow)
        docs/…   chỉ tài liệu (docs/rq-01)
        exp/…    thí nghiệm có thể bỏ (exp/umap-seeds) — không bắt buộc merge; xoá khi xong
```

Vì sao *luôn* worktree, kể cả việc nhỏ: chuyển nhánh ngay trong thư mục chính = đổi code cron chạy; một lần quên quay về `main` là cron chạy nhánh dở. Worktree tách hẳn chỗ làm khỏi chỗ chạy.

**1 nhánh = 1 đợt việc hoàn chỉnh** (1 ADR, hoặc 1 bước của plan). Đừng gom nhiều tuần vào 1 nhánh: PR càng to càng khó review, CI hỏng càng khó tìm chỗ.

**Nhánh xếp chồng** (việc B cần code của việc A chưa merge): tách B từ nhánh A, mở PR của B *sau* khi A đã merge — GitHub sẽ chỉ hiện commit của B.

## 4. Vòng đời 1 nhánh

Đường dẫn thư mục chính dưới đây viết tắt là `<CHÍNH>` = `C:\Users\hmnth\Desktop\Portfolio\project_AI\threads-ai-content`.

| Bước | Ai | Lệnh / thao tác |
|---|---|---|
| 1. Bắt đầu | Claude (`/git-flow start`) | `git fetch origin` → `git -C <CHÍNH> worktree add --no-track -b <nhánh> .claude/worktrees/<tên> origin/main` (luôn `-C <CHÍNH>`: chạy từ trong 1 worktree khác cũng không tạo worktree lồng nhau; `--no-track`: không để nhánh mới "theo dõi" `origin/main` — nếu không, `git status -sb` hiện `[origin/main: ahead N]` dù nhánh CHƯA push lần nào) → mở phiên Claude Code trong worktree đó (công cụ worktree của Claude Code) |
| 2. Chuẩn bị | Claude | copy `<CHÍNH>\.env` sang worktree (cách thủ công không tự copy); `uv sync --frozen`; dashboard: `npm install` trong `src/dashboard`; cần data → **copy** `data/threads.db` (bản nháp, không copy ngược lại — `/wt`) |
| 3. Làm + commit nhỏ | Claude, Thy duyệt | `/checkpoint` sau mỗi bước xanh; review tầng 2 trước commit logic/ADR (ADR-0015) |
| 4. Đẩy lên GitHub | **Thy** (lệnh push của Claude bị chặn) | `git push -u origin <nhánh>` (chạy được từ bất kỳ thư mục nào của repo) |
| 5. Mở PR | Thy | GitHub → `Compare & pull request`, hoặc `https://github.com/hmnthy/threads-ai-content/compare/main...<nhánh>` |
| 6. Chờ CI | Thy/Claude | Tab *Checks* của PR phải xanh (job `py` + `web`). CI chỉ chạy khi mở/cập nhật PR hoặc push vào `main` — push 1 nhánh thường không chạy CI. Đỏ → sửa trên cùng nhánh, push lại |
| 7. Merge | Thy | Nút **Create a merge commit** (không chọn Squash/Rebase) → *Delete branch* trên GitHub |
| 8. Cập nhật thư mục chính | Claude/Thy | Ở `<CHÍNH>`: `git checkout main` (nếu chưa ở main) → `git pull` → **luôn** `uv sync --frozen` (nhanh, chạy lại vô hại; cron chạy thẳng `.venv`, không tự sync — thiếu bước này là cron lỗi import khi PR thêm thư viện). Chạy khi `uv run python -m scripts.job_health` không báo "task running now" (job đang chạy giữ khoá file `.pyd`, sync có thể hỏng giữa chừng). Thư viện ML trong WSL `~/threads-clustering-env` không nằm trong `uv.lock` — cài riêng |
| 9. Dọn | Claude (`/wt clean <nhánh>`) | `git fetch --prune` → kiểm `git branch --merged origin/main` có nhánh → xoá worktree + nhánh local |

## 5. Tình huống thường gặp

- **Lỡ sửa code ở thư mục chính** → đừng commit ở đó; chuyển sang worktree bằng patch (đường dẫn tuyệt đối, ghi file bằng `--output` — PowerShell 5.1 ghi `>` thành UTF-16 làm hỏng patch):
  1. Ở `<CHÍNH>`: file mới chưa track → `git add -N <file mới>`; rồi `git diff HEAD --binary --output=C:\Users\hmnth\fix.patch`.
  2. Tạo worktree (mục 4 bước 1), trong worktree: `git apply --3way C:\Users\hmnth\fix.patch`; kiểm `git status` thấy đủ file (`--3way` đưa thay đổi vào trạng thái *staged* — đã đánh dấu chờ commit — là bình thường).
  3. Chỉ khi bước 2 đúng, ở `<CHÍNH>`: file sửa → `git restore --staged --worktree <file>`; file mới → `git rm --cached <file mới>` rồi xoá file; cuối cùng xoá `fix.patch`.
  Hook đầu phiên cảnh báo khi thư mục chính có code cron chưa commit.
- **Hook đầu phiên báo "thư mục chính đang ở `<nhánh>`"** → còn việc chưa merge. Merge PR rồi làm bước 8 ở thư mục chính.
- **Hook báo "`main` local chậm N commit so với `origin/main`"** → PR đã merge nhưng thư mục chính chưa pull → bước 8. **"`main` local có N commit chưa có trên `origin/main`"** → có commit thẳng lên main: dừng lại, hỏi Claude trước khi push.
- **`main` trên GitHub có commit mới trong lúc nhánh đang làm** → trong worktree: `git fetch origin` → `git merge origin/main` (không phải `git merge main`: `main` trên máy chỉ đổi khi pull ở thư mục chính nên có thể cũ), sửa xung đột nếu có, chạy lại test.
- **Xung đột (conflict)** → git đánh dấu `<<<<<<<` / `>>>>>>>` trong file. Giữ phần đúng, xoá dấu, `git add`, commit. Không chắc → hỏi Claude, đừng chọn bừa.
- **Xoá nhánh** → `git branch -d` chỉ xoá nhánh đã merge *vào upstream của nó hoặc vào HEAD* — nhánh đã push mà PR bị đóng không merge vẫn có thể bị xoá nếu `origin/<nhánh>` còn trên máy. Luôn kiểm `git branch --merged origin/main` sau `git fetch --prune` trước khi xoá (`/wt clean` làm việc này).
- **Claude Cowork** ghi thẳng vào thư mục nó mở → luôn mở Cowork trong 1 worktree riêng, không trong thư mục chính. **Claude Design** không kết nối git (chỉ đọc file) → không tạo nhánh được; thiết kế chỉ vào repo khi Claude Code port sang code.
- **Muốn xem cây nhánh** → VS Code: Source Control → *Graph* (hoặc extension *Git Graph*); terminal: `git log --graph --oneline --decorate --all`; GitHub: trang compare của nhánh.

## 6. Lệnh tra nhanh

```bash
git status -sb                              # nhánh nào; [ahead N] = N commit chưa push; không có [origin/…] = chưa push lần nào
git branch -vv                              # mọi nhánh local + nhánh GitHub tương ứng
git worktree list                           # các thư mục làm việc + nhánh của chúng
git log --oneline origin/main..<nhánh>      # commit của nhánh chưa có trên main (GitHub)
git branch --merged origin/main             # nhánh đã merge — xoá được
uv run python -m scripts.git_hygiene        # đúng các cảnh báo hook đầu phiên in ra (chạy ở thư mục repo)
```
