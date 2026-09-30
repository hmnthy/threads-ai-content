"""PostToolUse hook (Edit|Write): tự format + lint file Python vừa sửa.

Chạy `ruff format` rồi `ruff check --fix` đúng 1 file. Lỗi lint còn lại (không tự sửa được)
in ra stderr + exit 2 → Claude thấy và sửa tiếp (PostToolUse không chặn được, chỉ phản hồi).
Bỏ qua file ngoài repo, file trong `.claude/` và `tools/` (vendored, ruff đã exclude).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

payload = json.load(sys.stdin)
file_path = payload.get("tool_input", {}).get("file_path")
if not file_path or not str(file_path).endswith(".py"):
    sys.exit(0)

project = Path(os.environ.get("CLAUDE_PROJECT_DIR", payload.get("cwd", "."))).resolve()
target = Path(file_path).resolve()
try:
    rel = target.relative_to(project)
except ValueError:
    sys.exit(0)
if rel.parts and rel.parts[0] in {".claude", "tools", ".venv"}:
    sys.exit(0)
if not target.exists():
    sys.exit(0)

ruff = [sys.executable, "-m", "ruff"]
subprocess.run([*ruff, "format", "--quiet", str(target)], cwd=project, check=False)
result = subprocess.run(
    [*ruff, "check", "--fix", "--quiet", str(target)],
    cwd=project,
    capture_output=True,
    text=True,
    check=False,
)
if result.returncode != 0:
    print(f"ruff found issues it could not auto-fix in {rel}:\n{result.stdout}", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
