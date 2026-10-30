# ADR-0027: Repo public giữ mọi quyền; harness Claude Code `.claude/` riêng tư

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-30
- **Người quyết**: Thy (tác giả) — đề xuất bởi Claude, Thy chọn 2026-10-30

## Bối cảnh

- Repo `threads-ai-content` đã chuyển sang **public** trên GitHub. Trước đó, kế hoạch là giữ repo private và curate
  sang một repo public riêng (CLAUDE.md, mục "Trước khi public repo" của `docs/roadmap.md`). Thy quyết định public luôn
  repo hiện tại vì không có thời gian duy trì 2 repo.
- Kiểm tra ngày 2026-10-30, trên bản hiện tại và cả 104 commit lịch sử: không có token/secret thật (3 chỗ khớp mẫu đều
  là token giả trong test), không có `.env`, `data/`, `content/` hay file DB. Có 2 file `docs/research/*.html` từng
  được commit ở `8af3f30` rồi gỡ ở `74d144c` — vẫn đọc được trong lịch sử. Đó là báo cáo nghiên cứu, không có dữ liệu
  cá nhân.
- `.claude/` (32 file: 7 agent, 10 skill, 7 hook, 6 rule, `settings.json`) là bộ harness điều khiển Claude Code của dự
  án — tài sản riêng của tác giả, có thể được cấp phép riêng. Repo không có file `LICENSE`, nên về pháp lý đang ở chế độ
  mặc định "giữ mọi quyền", nhưng README ghi "Private personal project" và badge `license-private` — sai với repo public.
- `tools/ui-ux-pro-max/` là công cụ của bên thứ ba (Next Level Builder, giấy phép MIT —
  https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) được copy vào repo **không kèm** thông báo giấy phép, trái với
  điều kiện duy nhất của MIT.

## Quyết định

1. **Repo public giữ mọi quyền**: thêm file `LICENSE` ("All rights reserved" — được xem, không được dùng, sửa, phân
   phối hay bán khi chưa có giấy phép bằng văn bản của tác giả); thành phần bên thứ ba giữ giấy phép gốc
   (`tools/ui-ux-pro-max/LICENSE`, MIT). README 3 ngôn ngữ đổi badge + mục giấy phép cho khớp. Không dùng MIT cho
   phần của tác giả (MIT cho phép bất kỳ ai dùng và bán lại code miễn phí).
2. **`.claude/` thôi được repo này theo dõi** (gitignored) từ commit của ADR này. Lịch sử của harness nằm trong một kho
   git riêng dạng *bare* đặt **ngoài** `.claude/` (`<thư mục chính>\..\threads-harness.git`, thư mục làm việc =
   `.claude/` của thư mục chính; khởi tạo từ `git subtree split --prefix=.claude`, giữ đủ lịch sử cũ), có thể đẩy lên một
   repo **private** để sao lưu. Không đặt `.git` trong `.claude/`: git coi đó là repo lồng và không liệt kê file bên
   trong, nên `.worktreeinclude` sẽ âm thầm không copy harness sang worktree. Lịch sử cũ của repo public **không viết lại** — bản harness đã public
   được bảo vệ bằng quyền tác giả, không bằng kỹ thuật.
3. **Công cụ kiểm vẫn phủ harness trên máy**: sổ luật coi `.claude/**` là "có trên máy, không có ở clone mới/CI"
   (`known_untracked`); `check --all` (dùng trong `/decision-sweep`) quét thêm file harness trên đĩa nếu có;
   `--commit` (pre-commit) và CI không quét nội dung harness — chỉ kiểm đường dẫn `.claude/...` có thật trên đĩa khi
   máy có harness (dấu hiệu: có `.claude/settings.json`). Mọi chế độ (`--commit`, `--staged`, và `--all` mà CI chạy)
   **chặn** đường dẫn `.claude/` bị track hoặc stage (`git add -f` vượt `.gitignore`).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giấy phép MIT cho cả repo | Người khác dùng lại dễ | Cho phép bất kỳ ai dùng và bán lại code + harness miễn phí | Đi ngược mục tiêu giữ quyền với harness |
| Giữ `.claude/` trong repo public | Không phải đổi quy trình; người đọc thấy harness | Harness lộ ở mọi bản mới | Thy muốn harness riêng tư |
| Repo public mới sạch (1 commit, không `.claude/`), repo cũ chuyển private | Sạch nhất, không lịch sử | Đồng bộ 2 repo mỗi lần cập nhật; mất dấu 104 commit / 24 PR | Tốn công duy trì khi Thy đang bận |
| Viết lại lịch sử (`git filter-repo` + force push) | Xoá harness + `docs/research/` khỏi lịch sử | Không hoàn tác được; GitHub vẫn giữ bản cũ qua ref của 24 PR tới khi GitHub Support xoá; bản clone đã có vẫn còn | Rủi ro và công sức lớn hơn lợi ích |

## Hệ quả

- File đổi: `LICENSE` (mới), `tools/ui-ux-pro-max/LICENSE` (mới), `.gitignore` (`.claude/`), `.worktreeinclude`
  (bản sao harness chỉ đọc), README 3 bản (badge + mục giấy phép + liên hệ cấp phép; bỏ "open-sourced-in-spirit"),
  `docs/status.md`, `docs/design/ui-contract.md` (`UI-0027-no-ui-impact`), `docs/decisions/invariants.toml` (`known_untracked` + luật dưới), `scripts/consistency/check.py`
  (`--all` quét harness trên đĩa) + test, `scripts/review_gate.py` (bỏ `.claude/...` khỏi `REVIEW_SCOPE` — không bao giờ
  stage được nữa) + test, CLAUDE.md, `docs/claude/architecture.md`, `docs/claude/git-workflow.md`,
  `docs/claude/dev-rules.md`, `docs/decisions/README.md` (chú thích thu hẹp ở dòng 0015, 0019), `docs/roadmap.md`
  (mục "Trước khi public repo" thay bằng ADR này).
- Harness cần sửa theo ADR này (trong kho riêng, sau khi merge): docstring `guard_commit.py`, skill `git-flow` / `wt` /
  `checkpoint` / `record-decision` / `decision-sweep`, mô tả agent `code-reviewer` — bỏ giả định `.claude/` đi qua nhánh,
  PR, `review-gate`.
- **Thu hẹp ADR-0015 và ADR-0019 cho `.claude/`**: sửa harness làm thẳng ở `.claude/` của thư mục chính và commit vào
  kho riêng — không qua nhánh → PR → CI, và git hook `review-gate` không thấy các commit đó. `@agent-code-reviewer`
  vẫn nên được gọi trước khi commit hook/agent/settings (theo thói quen, không còn máy chặn). Git không đưa `.claude/`
  vào worktree → bước chuẩn bị worktree copy một bản **chỉ đọc** (`docs/claude/git-workflow.md` bước 2;
  `.worktreeinclude` cho worktree tạo bằng công cụ Claude Code) để agent, hook, dấu review (ADR-0015) và rule tự nạp vẫn
  chạy trong worktree.
- Test đọc file harness thật (`guard_commit.py`, `settings.json` trong `tests/scripts/test_review_gate.py`) được bỏ qua
  khi máy không có harness (CI, clone, worktree chưa copy) và assert file tồn tại để không "xanh giả".
- Khi thư mục chính `git pull` commit của ADR này, Git **xoá** các file `.claude/` đang được theo dõi khỏi đĩa. Thứ tự:
  sao lưu (bản 2026-10-30 nằm ngoài repo, gồm file + bundle lịch sử) → `git pull` → khôi phục file → tạo kho bare
  `git init --bare -b main threads-harness.git` → `git --git-dir=threads-harness.git fetch <bundle>
  tmp-harness-history:main` (bundle chỉ có nhánh đó, không có HEAD — `clone --bare` sẽ để HEAD trỏ nhánh rỗng và tách
  đôi lịch sử) → kiểm `log --oneline -1` ra commit cuối của harness → ghi `worktrees/`, `settings.local.json`,
  `agent-memory/`, `agent-memory-local/` (ghi chú subagent = dữ liệu của máy) vào `info/exclude` → `git --git-dir=…
  --work-tree=<thư mục chính>\.claude reset` (chỉ nạp index, giữ file đã khôi phục) → `status` sạch. Giữa lúc pull và khôi phục, hook SessionStart/guard không chạy.
- Kiểm đường dẫn chết: có harness trên máy thì đường dẫn `.claude/...` được kiểm thật trên đĩa (cả `--commit`);
  `known_untracked` chỉ cho qua khi máy không có harness. `ruff check .` (pre-commit/CI) không còn lint hook harness —
  chỉ còn hook `ruff_on_edit` khi sửa.
- Rủi ro chấp nhận: harness chỉ còn 1 bản trên laptop tới khi kho riêng được đẩy lên repo private; luật `[[forbid]]`
  có `paths` gồm `.claude/**` chỉ chạy ở `check --all` trên máy có harness.
- Luật mới: `ADR0027-private-repo-wording` (README/CLAUDE.md/docs không còn gọi repo là private hay hứa "curate sang
  repo public riêng"; badge không còn `license-private`), `ADR0027-open-source-claim` (không tự gọi là open source), `ADR0027-harness-not-tracked` (trong
  `check.py`, không phải regex). `known_untracked` thêm `.claude`, `.claude/**`. Badge số test đếm cả 45 test cần harness
  (CI / clone công khai bỏ qua chúng) — chấp nhận.
- Xem lại khi: ký hợp đồng cấp phép harness (có thể cần điều khoản riêng trong `LICENSE`), hoặc khi chuyển sang mô hình
  2 repo (public curate + private làm việc).

### Hệ quả UI

- Dòng `docs/design/ui-contract.md` thêm: `UI-0027-no-ui-impact` (không có hệ quả UI — giấy phép và harness không
  hiển thị trên dashboard hay landing).
