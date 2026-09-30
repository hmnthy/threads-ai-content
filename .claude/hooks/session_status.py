"""SessionStart hook: in ≤30 dòng trạng thái để Claude định hướng nhanh mà không đọc cả docs.

stdout của SessionStart được đưa thẳng vào context (docs: code.claude.com/docs/en/hooks).
Giữ ngắn — mọi dòng in ra ở đây tốn context mỗi phiên.
"""

import os
import subprocess
import sys
from pathlib import Path

# Windows mặc định stdout cp1252 → vỡ khi in tiếng Việt / ký tự "→".
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

project = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


lines: list[str] = ["## Session status (auto, .claude/hooks/session_status.py)"]

branch = git("branch", "--show-current") or "(detached)"
dirty = [line for line in git("status", "--porcelain").splitlines() if line]
lines.append(f"- Branch: `{branch}` — {len(dirty)} uncommitted file(s)")
if dirty:
    lines.append("  → If the last step is green, propose `/checkpoint`.")
lines.append("- Last commits:")
lines += [f"  - {c}" for c in git("log", "-3", "--format=%h %s (%cr)").splitlines()]

status_md = project / "docs" / "status.md"
if status_md.exists():
    text = status_md.read_text(encoding="utf-8").splitlines()
    block: list[str] = []
    capture = False
    for line in text:
        if line.startswith("## "):
            capture = line[3:].strip().lower().startswith(("now", "next", "blocked"))
        if capture and line.strip():
            block.append(line)
    if block:
        lines.append("- From docs/status.md:")
        lines += [f"  {line}" for line in block[:12]]

logs = project / "data" / "logs"
for name in ("scheduled_job.log", "nlp_cluster_job.log"):
    log = logs / name
    if log.exists():
        tail = [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln]
        if tail:
            lines.append(f"- Last line of {name}: {tail[-1][:160]}")

print("\n".join(lines[:30]))
