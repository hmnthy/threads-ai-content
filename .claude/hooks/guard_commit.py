"""PreToolUse hook (Bash, PowerShell): chặn `git commit` vi phạm quy tắc repo.

- Không trailer `Co-Authored-By` (repo sẽ được curate sang bản public, xem CLAUDE.md).
- Không `--no-verify` (bỏ qua pre-commit = bỏ qua ruff, mypy, consistency, pytest nhanh,
  dashboard, cổng review tầng 2, commit-msg).
- Không lách git hook pre-commit (ADR-0015): `SKIP=` của pre-commit, gỡ/gán lại `CLAUDECODE`
  (cổng review chỉ chạy khi =1), đổi `core.hooksPath`. Best-effort — chặn đường lách VÔ TÌNH
  thường gặp; ngoài tầm (ghi trong ADR-0015): `git config core.hooksPath` chạy riêng,
  `pre-commit uninstall`, sửa tay `stamps.json`.

Cổng review tầng 2 KHÔNG nằm ở đây mà ở git hook pre-commit (`scripts/review_gate.py check`):
hook PreToolUse chạy trước lệnh nên không thấy index cuối cùng của `git add … && git commit`,
không biết repo của `git -C <dir> commit`.

Exit 2 + stderr = chặn tool call và đưa lý do cho Claude (docs: code.claude.com/docs/en/hooks).
Chỉ dùng thư viện chuẩn.
"""

import json
import re
import sys

# Thứ tự xử lý (bài học 6 vòng review 2026-10-01): nối dòng tiếp diễn → bỏ thân message →
# kiểm TỪNG lệnh `git commit` trong chuỗi, không chỉ lệnh đầu.
CONTINUATION = re.compile(r"\\\r?\n|`\r?\n")  # bash `\⏎`, PowerShell `` `⏎ ``
# `commit` phải là LỆNH CON của git (sau tuỳ chọn toàn cục `-C x`, `-c k=v`, `--x`) — không
# khớp chuỗi con trong đường dẫn như .git/hooks/pre-commit hay .pre-commit-config.yaml.
GIT_COMMIT = re.compile(
    r"\bgit(?:\s+(?:-[cC]\s+(?:\"[^\"]*\"|'[^']*'|\S+)|--?[\w.-]+(?:=\S+)?))*\s+commit\b"
)
QUOTED = re.compile(r'"(?:\\.|[^"\\])*"|\'[^\']*\'')
# Nội dung commit message (không phải cờ): heredoc bash (chỉ THÂN — giữ dòng mở:
# `cat <<'EOF' | SKIP=… git commit -F -`), here-string PowerShell, đối số -m (kể cả `-am`,
# `-m"x"`) / --message. Dòng kết thúc heredoc phải đứng riêng (dòng "EOF handling…" không tính).
HEREDOC = re.compile(r"(<<-?\s*['\"]?(\w+)['\"]?[^\n]*)\n.*?\n[ \t]*\2[ \t]*(?=\r?\n|$)", re.DOTALL)
HERESTRING = re.compile(r"@(['\"])\r?\n.*?\r?\n\1@", re.DOTALL)
MESSAGE_ARG = re.compile(
    r"(?:-[A-Za-z]*m|--message)(?:=|\s+)?(?:\"(?:\\.|[^\"\\])*\"|'[^']*'|[^\s;&|]+)"
)
# Hết 1 lệnh: &&, ||, |, |&, &, ;, xuống dòng — `&` của redirect (`2>&1`, `&>`) KHÔNG tính
COMMAND_END = re.compile(r"&&|\|\|?&?|(?<![<>])&(?!>)|;|\n")
# `\s*=`: PowerShell viết `$env:SKIP = 'x'`
BYPASS = re.compile(r"\bSKIP\s*=|\bCLAUDECODE\b|\bhooksPath\b", re.IGNORECASE)
# --no-verify (git nhận cả dạng viết tắt `--no-veri`), hoặc -n riêng / gộp sau cờ ngắn không
# nhận giá trị (`-nm`, `-qn`)
NO_VERIFY = re.compile(r"--no-v(?:e(?:r(?:i(?:fy?)?)?)?)?\b|\s-[aeiopqsvz]*n")


def end_of_command(text: str, start: int) -> int:
    tail = COMMAND_END.search(text, start)
    return tail.start() if tail else len(text)


payload = json.load(sys.stdin)
command = CONTINUATION.sub(" ", str(payload.get("tool_input", {}).get("command", "")))

commits = list(GIT_COMMIT.finditer(command))
if not commits:
    sys.exit(0)

# Chỉ bắt trailer thật (dòng bắt đầu bằng "Co-Authored-By:" hoặc --trailer), không bắt
# message chỉ NHẮC tới quy tắc này — VD "block commits carrying a Co-Authored-By trailer".
trailer = r"(^|\n|\\n)[ \t]*co-authored-by[ \t]*:|--trailer[= ]+[\"']?co-authored-by"
if re.search(trailer, command[commits[0].start() :], re.IGNORECASE):
    print(
        "Blocked: commit message must not contain a Co-Authored-By trailer (repo rule, "
        "see CLAUDE.md). Remove the trailer and retry.",
        file=sys.stderr,
    )
    sys.exit(2)

# Cờ thật của TỪNG lệnh commit (bỏ message; tới `|`, `&`, `;`, xuống dòng: `git commit … 2>&1 |
# tail -n 20` không phải -n). `git commit -m x || git commit --no-verify …` cũng bị bắt.
stripped = QUOTED.sub("", HERESTRING.sub("", HEREDOC.sub(r"\1", command)))
for m in GIT_COMMIT.finditer(stripped):
    if NO_VERIFY.search(stripped[m.start() : end_of_command(stripped, m.end())]):
        print(
            "Blocked: --no-verify skips the ruff, mypy, consistency, fast-test, tier-2 review, "
            "dashboard and commit-msg hooks. Fix the hook failure instead.",
            file=sys.stderr,
        )
        sys.exit(2)

# Đường lách: quét từ ĐẦU lệnh (cả các dòng trước: `git add -A⏎SKIP=… git commit`) tới HẾT
# lệnh commit cuối, GIỮ nội dung trong nháy (`git -c "core.hooksPath=x"`, `bash -c 'SKIP=… git
# commit'`) — chỉ bỏ commit message. Lệnh sau commit (VD `| grep CLAUDECODE`) không tính.
without_message = MESSAGE_ARG.sub("", HERESTRING.sub("", HEREDOC.sub(r"\1", command)))
found = list(GIT_COMMIT.finditer(without_message))
end = end_of_command(without_message, found[-1].end()) if found else len(without_message)
bypass = BYPASS.search(without_message[:end])
if bypass:
    print(
        f"Blocked: '{bypass.group(0)}' on a commit command bypasses the pre-commit gates "
        "(incl. the tier-2 review gate, ADR-0015). Fix the failing hook or get the review.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
