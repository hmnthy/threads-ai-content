# ADR-0015: Bắt buộc review tầng 2 trước commit — dấu review khớp nội dung + git hook chặn

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-01
- **Người quyết**: Thy chọn phương án A + B (2026-10-01, "cách đảm bảo hơn cho code-reviewer"); Claude thiết kế

## Bối cảnh

ADR-0008 đặt tầng 2 (`code-reviewer`, `consistency-auditor`) nhưng chỉ chạy khi có người nhớ gọi. Bằng chứng tầng 2 bắt được thứ tầng 1 và test không bắt:

- 2026-10-01, ADR-0004: phân vai reply theo timestamp sai 67 reply; so DBCV khác thang; migration không nguyên tử; ARI gộp 2 thay đổi — đều do code-reviewer bắt trước commit.
- 2026-10-01, ADR-0013/0014: 4 vòng review bắt ~30 điểm, trong đó 1 test sẽ hỏng trên CI Linux mà máy Windows không thấy, checker bỏ qua file chưa track.

Skill `/checkpoint` chỉ ghi "đề xuất gọi `@agent-code-reviewer`" — không có gì chặn commit thiếu review.

## Quyết định

1. **(A) Dấu review khớp nội dung.** Hook `SubagentStart`/`SubagentStop` (matcher `code-reviewer|consistency-auditor`) gọi `scripts/review_gate.py start|stop`: chụp blob hash (mã băm nội dung git) của bản **trên đĩa** — bản agent đọc được — của các file trong phạm vi đang khác HEAD, lúc agent bắt đầu và kết thúc. Ghi dấu chỉ khi đủ cả: blob **không đổi suốt lượt**; transcript của agent có lệnh `git diff`/`status`/`show` (bằng chứng tối thiểu đã đọc thay đổi); chỉ ở worktree của phiên (cwd của hook — review worktree khác thì chạy agent từ phiên mở ở worktree đó); đúng việc được giao (code-reviewer → file logic; consistency-auditor → ADR được nhắc rõ dạng `ADR-NNNN`/`decisions/NNNN`). Bản trong index KHÔNG được ghi dấu (stage bản cũ rồi sửa trên đĩa → bản index chưa được review). Dấu ở `<git-common-dir>/claude-review/` (dùng chung mọi worktree vì khoá theo nội dung; khoá file + ghi nguyên tử; tự dọn dấu của nội dung không còn ở đâu ngoài HEAD; không bao giờ vào commit).
2. **(A) Git hook pre-commit chặn** (`review-gate` trong `.pre-commit-config.yaml`, `review_gate.py check`), chỉ khi `CLAUDECODE=1` (shell của Claude Code): mỗi file sắp commit (index so với HEAD, không dò rename) trong phạm vi logic — `src/**/*.py`, dashboard `src/`, `package.json`, file cấu hình, `scripts/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/agents/**`, `.github/workflows/**`, `.pre-commit-config.yaml`, `pyproject.toml`, `invariants.toml` — phải có dấu code-reviewer khớp blob; ADR (`docs/decisions/NNNN-*.md`) phải có dấu consistency-auditor. Lỗi git → chặn (fail closed).
3. **(B) `/checkpoint` bắt buộc review**: reviewer trên TOÀN BỘ diff sau lần sửa cuối, sửa phát hiện, chạy lại tới khi sạch; báo phát hiện cho Thy khi xin commit.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| B riêng (chỉ sửa skill) | Rẻ | Vẫn dựa vào việc nhớ làm theo | Thy chọn cách đảm bảo hơn |
| A với dấu "đã review trong phiên" (không theo nội dung) | Đơn giản | Sửa code sau review vẫn commit được | Không chặn đúng lỗi hay gặp |
| Kiểm ở hook PreToolUse của lệnh Bash `git commit` (bản đầu) | Không cần pre-commit | Chạy TRƯỚC lệnh: `git add -A && git commit` lọt (index cũ), `git -C <dir> commit` kiểm nhầm repo, chặn nhầm lệnh chỉ chứa chữ "git commit" — code-reviewer tái hiện cả 3 | Thay bằng git hook (thấy index cuối, đúng repo) |
| Ghi dấu cả bản index + mọi worktree (bản thứ 2) | Đơn giản | Dấu cho nội dung agent không đọc (bản index cũ hơn đĩa; worktree của phiên khác) — code-reviewer tái hiện | Chỉ bản đĩa + worktree của phiên (bản thứ 3 sửa tiếp vế worktree) |
| Đoán worktree agent nhìn vào từ đường dẫn trong prompt/lệnh (bản thứ 3) | Review chéo worktree | So chuỗi con: worktree của `/wt` nằm TRONG checkout chính → đóng dấu nhầm checkout chính (code-reviewer tái hiện) | Chỉ worktree của phiên |
| Git hook pre-commit + biến `CLAUDECODE` (chọn) | Index cuối cùng (kể cả `commit -a`, pathspec); đúng repo/worktree; Thy commit tay không bị ảnh hưởng | Cần `pre-commit install` (đã có) | — |

## Hệ quả

- Đổi: `scripts/review_gate.py`, `.pre-commit-config.yaml` (hook `review-gate`, đặt trước pytest-fast), `tests/conftest.py` (xoá biến `GIT_*` cho mọi test — git hook xuất `GIT_INDEX_FILE` tuyệt đối của repo thật; test repo tạm thừa hưởng là ghi đè index thật, đã xảy ra khi review), `.claude/settings.json` (2 hook SubagentStart/Stop + nối `guard_commit.py` cho lệnh Bash bắt đầu bằng `git`/`env`/`bash`/`sh` và mọi lệnh PowerShell), `.claude/hooks/guard_commit.py` (chặn đường lách vô tình `SKIP=`/`CLAUDECODE`/`core.hooksPath`; cổng chính vẫn ở git hook), `.claude/rules/python.md`, `docs/claude/dev-rules.md`, `docs/roadmap.md` (Phase C: 5 entry pre-commit), `docs/decisions/{README.md,invariants.toml}`, `tests/scripts/test_consistency.py`, `.claude/skills/{checkpoint,decision-sweep,record-decision,wt}/SKILL.md`, `.claude/agents/{code-reviewer,consistency-auditor}.md`, `CLAUDE.md`, `docs/claude/architecture.md`; test `tests/scripts/test_review_gate.py` (chạy `git commit` thật với git hook trên repo tạm).
- Hook SubagentStart/Stop có hiệu lực ngay trong phiên đã sửa `settings.json` (kiểm 2026-10-01: dấu được ghi khi auditor chạy xong).
- Ngoài phạm vi review bắt buộc (có chủ đích): `tests/` (qa-tester), docs, skills/rules (chỉ dẫn văn bản), lockfile (máy sinh — `pyproject.toml`/`package.json` khai báo phụ thuộc thì có trong phạm vi).
- Giới hạn chấp nhận: dấu chứng minh "agent đã chạy lệnh xem diff, file không đổi suốt lượt" — không chứng minh "review sạch"; phần đó do bước B + Thy đọc báo cáo. Lượt review hẹp vẫn đóng dấu mọi file logic đang đổi → `code-reviewer.md` buộc luôn quét toàn bộ diff.
- Lối thoát khi cổng hỏng: Thy commit tay từ terminal NGOÀI Claude Code (lệnh `!` trong Claude Code cũng có `CLAUDECODE=1` nên vẫn bị chặn). Với Claude, hook PreToolUse `guard_commit.py` (lệnh Bash bắt đầu bằng `git`/`env`/`bash`/`sh`, và mọi lệnh PowerShell) chặn các đường lách VÔ TÌNH thường gặp — best-effort, không phải hàng rào an ninh: `--no-verify`, `SKIP=` của pre-commit, gỡ/gán lại `CLAUDECODE`, đổi `core.hooksPath`. Ngoài tầm: `git config core.hooksPath` chạy riêng, `pre-commit uninstall`, sửa tay `stamps.json`, và các lệnh tạo commit không chạy pre-commit (`git commit-tree` + `update-ref`, cherry-pick, revert, rebase) — dựa vào quy tắc + Thy đọc lịch sử.
- Commit 1 phần (stage 1 phần, `git rm --cached` file logic): bản index khác bản đĩa không bao giờ được ghi dấu → đưa đĩa về đúng bản sẽ commit (stash phần còn lại) rồi review; hoặc Thy commit tay.
- Merge có xung đột: file có nội dung y nguyên bản ở `MERGE_HEAD` (hoặc bị xoá mà nhánh kia thật sự đã xoá) không cần dấu — đã qua cổng trên nhánh kia; phần do lần merge tạo ra (giải xung đột, file tự gộp từ 2 phía) phải review. `git merge --squash` không có `MERGE_HEAD` → review lại cả diff nhánh (chặt thừa, không lọt). Merge không xung đột không chạy pre-commit (`pre-merge-commit` không được cài) → nội dung tự gộp từ 2 phía đã review không bị review lại — chấp nhận.
- Race chấp nhận: 2 agent kết thúc gần như cùng lúc có thể làm mất dấu của nhau (dọn dấu tính ngoài khoá) → hậu quả là chặn thừa (review lại), không bao giờ lọt.
- Luật: `ADR0015-optional-review` cấm mô tả review là tuỳ chọn ("đề xuất gọi `@agent-code-reviewer`").
- Xem lại khi: thêm thư mục code mới (mở rộng `REVIEW_SCOPE`), hoặc chi phí review làm chậm commit quá mức (Thy đánh giá).
