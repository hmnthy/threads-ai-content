"""PreToolUse hook (Bash): chặn `git commit` vi phạm quy tắc repo.

- Không trailer `Co-Authored-By` (repo sẽ được curate sang bản public, xem CLAUDE.md).
- Không `--no-verify` (bỏ qua pre-commit = bỏ qua ruff, mypy, consistency, pytest nhanh,
  dashboard, commit-msg).

Exit 2 + stderr = chặn tool call và đưa lý do cho Claude (docs: code.claude.com/docs/en/hooks).
Chỉ dùng thư viện chuẩn.
"""

import json
import re
import sys

payload = json.load(sys.stdin)
command = str(payload.get("tool_input", {}).get("command", ""))

match = re.search(r"\bgit\b[^;&|]*?\bcommit\b", command, re.DOTALL)
if not match:
    sys.exit(0)
# Chỉ xét phần từ `git … commit` trở đi — tránh bắt nhầm `git log -n 3 && git commit …`.
commit_part = command[match.start() :]

# Chỉ bắt trailer thật (dòng bắt đầu bằng "Co-Authored-By:" hoặc --trailer), không bắt
# message chỉ NHẮC tới quy tắc này — VD "block commits carrying a Co-Authored-By trailer".
trailer = r"(^|\n|\\n)[ \t]*co-authored-by[ \t]*:|--trailer[= ]+[\"']?co-authored-by"
if re.search(trailer, commit_part, re.IGNORECASE):
    print(
        "Blocked: commit message must not contain a Co-Authored-By trailer (repo rule, "
        "see CLAUDE.md). Remove the trailer and retry.",
        file=sys.stderr,
    )
    sys.exit(2)

# Bỏ nội dung trong dấu nháy (commit message) — chỉ xét cờ thật của lệnh git.
flags_only = re.sub(r'"(?:\\.|[^"\\])*"|\'[^\']*\'', "", commit_part)
first_command = re.split(r"&&|\|\||;", flags_only)[0]
if re.search(r"--no-verify\b|\s-n\b", first_command):
    print(
        "Blocked: --no-verify skips the ruff, mypy, consistency, fast-test, dashboard and "
        "commit-msg hooks. Fix the hook failure instead.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
