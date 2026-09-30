"""PostToolUse hook (Edit|Write): khi Claude ghi 1 ADR, nhắc lan quyết định ra toàn repo.

Ghi/sửa `docs/decisions/NNNN-*.md` (trừ 0000-template) → đưa vào context của Claude lời
nhắc chạy `/decision-sweep NNNN`. Dùng JSON `additionalContext`
(docs: code.claude.com/docs/en/hooks) — không chặn, chỉ nhắc. Chỉ dùng thư viện chuẩn.
"""

import json
import re
import sys

payload = json.load(sys.stdin)
file_path = str(payload.get("tool_input", {}).get("file_path", "")).replace("\\", "/")
m = re.search(r"docs/decisions/(\d{4})-[^/]+\.md$", file_path)
if not m or m.group(1) == "0000":
    sys.exit(0)

adr = m.group(1)
message = (
    f"ADR-{adr} vừa được ghi. Quyết định chưa hoàn tất cho tới khi được lan ra toàn repo: "
    f"thêm luật vào docs/decisions/invariants.toml (nếu chưa có), rồi chạy /decision-sweep {adr} "
    "(kiểm kê tầng 1 + consistency-auditor → sửa → kiểm tra cuối)."
)
# ensure_ascii (mặc định) → chỉ xuất ASCII: stdout Windows là cp1252, in thẳng tiếng Việt sẽ sập
print(
    json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}
    )
)
sys.exit(0)
