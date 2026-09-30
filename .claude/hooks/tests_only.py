"""PreToolUse hook (Edit|Write) cho subagent qa-tester: chỉ cho sửa file trong `tests/`.

qa-tester viết/chạy test — sửa code sản phẩm là việc của phiên chính (sau khi đọc báo cáo).
Exit 2 + stderr = chặn và báo lý do cho subagent.
"""

import json
import os
import sys
from pathlib import Path

payload = json.load(sys.stdin)
file_path = payload.get("tool_input", {}).get("file_path") or payload.get("tool_input", {}).get(
    "notebook_path"
)
if not file_path:
    sys.exit(0)

project = Path(os.environ.get("CLAUDE_PROJECT_DIR", payload.get("cwd", "."))).resolve()
try:
    rel = Path(file_path).resolve().relative_to(project)
except ValueError:
    rel = None

if rel is None or not rel.parts or rel.parts[0] != "tests":
    print(
        f"qa-tester may only edit files under tests/ (got {file_path}). Report the product-code "
        "change you think is needed instead of making it.",
        file=sys.stderr,
    )
    sys.exit(2)
sys.exit(0)
