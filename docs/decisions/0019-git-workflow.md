# ADR-0019: Quy trình git — thư mục chính luôn ở `main`, mọi thay đổi trong worktree, PR + merge commit

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-05
- **Người quyết**: Thy (chọn: thư mục chính luôn ở `main`; merge kiểu merge commit; làm đủ tài liệu + skill + nhắc tự động + ADR), Claude đề xuất

## Bối cảnh

- Quy ước cũ (CLAUDE.md) chỉ có 1 câu: "không làm trực tiếp trên `main` cho việc nhiều bước — branch hoặc worktree". Không nói khi nào chọn cái nào, không có vòng đời nhánh, không có gì nhắc. Thy là người mới với git chuyên sâu và hỏi lại chính điều này (2026-10-05).
- Hệ quả thực tế:
  - Thư mục chính đứng ở nhánh `feat/dashboard-p1` từ 2026-10-01 → 2 cron (ADR-0013/0017) chạy code chưa qua PR/CI; `main` tụt 11 commit; CI (ADR-0014) chưa chạy lần nào vì chỉ chạy khi push `main` hoặc mở PR.
  - 2026-10-04: đang sửa ADR-0018 ngay trong thư mục chính → job snapshot 21:15 chạy bản nháp và migrate DB thật (id `cluster_N` → `topic_N`) trước khi Thy duyệt — cron chạy *mọi* file trên đĩa, kể cả chưa commit, và mọi job gọi `create_schema()`.
  - Thy tưởng Claude Design có thể đã tạo nhánh — thật ra nhánh do Claude tạo theo plan P1 (reflog: `branch: Created from HEAD` 2026-10-01 12:29:21); Claude Design không kết nối git (`dev-rules.md`). Thiếu một chỗ để tra "đang ở đâu, nhánh nào, vì sao".

## Quyết định

1. **Thư mục chính luôn ở `main`** và không sửa code ở đó — chỉ để cron chạy, xem dashboard/API trên data thật, `git pull` sau merge.
2. **Mọi thay đổi** (kể cả nhỏ) làm trên **nhánh mới từ `origin/main` (sau `git fetch`) trong worktree riêng** (`.claude/worktrees/<tên>`); tên nhánh `feat/ · fix/ · chore/ · docs/ · exp/`; 1 nhánh = 1 đợt việc hoàn chỉnh. Nhánh cần code chưa merge → nhánh xếp chồng, PR mở sau nhánh gốc.
3. **Không commit thẳng lên `main`**: nhánh → push (Thy) → PR → CI xanh → **Create a merge commit** (không squash/rebase — giữ từng commit ADR và các mã commit mà docs/memory nhắc) → xoá nhánh → `git pull` ở thư mục chính → dọn worktree.
4. **Nhắc tự động**: hook đầu phiên chạy `scripts/git_hygiene.py` (chỉ đọc) — cảnh báo khi thư mục chính không ở `main`, khi thư mục chính có code cron chưa commit, liệt kê nhánh chưa merge và worktree có việc dở. Skill `/git-flow status|start|finish` dẫn từng bước; tài liệu cho người mới `docs/claude/git-workflow.md`.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Thư mục chính đứng ở nhánh đang làm, merge theo đợt lớn | Ít thao tác | Cron chạy code chưa qua CI; `main` tụt xa; dễ chạy nhầm bản nháp (sự cố 2026-10-04) | Thy chọn `main` |
| Nhánh ngắn ngay trong thư mục chính cho việc nhỏ | Không cần worktree | Một lần quên quay về `main` = cron chạy nhánh dở; 2 quy tắc khó nhớ hơn 1 | "Luôn worktree" đơn giản, an toàn |
| Squash merge | `main` gọn | Mất từng commit ADR trong lịch sử `main` | Thy chọn merge commit |
| Rebase merge | Lịch sử thẳng, đủ chi tiết | Đổi mã commit — docs/memory nhắc `f908d8a`… sẽ sai | Như trên |
| Chặn cứng (hook từ chối) thay vì nhắc | Không thể quên | Chặn cả thao tác hợp lệ khi khẩn cấp; Thy đang học | Nhắc + skill trước; xem lại nếu vẫn tái diễn |

## Hệ quả

- Code: `scripts/git_hygiene.py` (+ `tests/scripts/test_git_hygiene.py`), `.claude/hooks/session_status.py` gọi nó (timeout hook SessionStart 20 → 25s, `.claude/settings.json`; quá giờ vẫn in phần đã có + dòng "timed out", không im lặng). Mọi `git status` nền dùng `--no-optional-locks` (không lấy `index.lock`, không chặn commit của phiên/tool khác). Danh sách "code cron" được giữ đúng bằng test dò đồ thị import của 2 cron. Kiểm thêm `main` local lệch `origin/main` (commit thẳng lên main / PR đã merge chưa pull). Đếm nhánh chưa merge bằng 1 lệnh `for-each-ref … %(ahead-behind:origin/main)` (không có `origin/main` thì so với `main`; cần git ≥ 2.41).
- `scripts/job_health.py` đo trên DB + log của **thư mục chính** kể cả khi phiên chạy trong worktree (worktree không có `data/threads.db` → trước đây báo WARN "no data" sai ở mọi phiên worktree).
- Skill mới `.claude/skills/git-flow/`; `/wt` (dọn: kiểm `git branch --merged origin/main`), `/checkpoint` (dừng nếu đang ở `main`/thư mục chính có thay đổi; xong → `/git-flow finish`), `/recluster` (thư mục chính phải ở `main`, không có code cron chưa commit) theo quy trình này.
- Docs: `docs/claude/git-workflow.md` (mới), CLAUDE.md (mục Git), `docs/claude/dev-rules.md` (Cowork mở trong worktree), `docs/claude/architecture.md`.
- Sổ luật: không có luật regex — hành vi được giữ bằng hook nhắc + test, không phải chữ trong docs (như ADR-0011).
- Việc kéo theo ngay: PR đầu tiên `feat/dashboard-p1` → `main` (CI chạy lần đầu), merge commit, rồi `git checkout main` ở thư mục chính. Nhánh này (`chore/git-workflow`) xếp chồng trên `feat/dashboard-p1` → PR mở sau.
- Trước Phase C: worktree có `data/threads.db` riêng (bản sao, có thể cũ) — xem/thử dashboard trên data thật thì ở thư mục chính sau khi merge, hoặc copy DB (bản nháp).
- Xem lại khi: hook vẫn báo thư mục chính rời `main` ≥ 2 lần/tháng (→ chặn cứng); Phase C (WSL, `run_job.sh`) — cron và DB chuyển chỗ, kiểm tra lại "code cron" trong `git_hygiene`; có người cộng tác thứ hai (→ branch protection trên GitHub).
