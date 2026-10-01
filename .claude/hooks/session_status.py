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


# Mỗi subprocess có timeout < timeout của hook (20s, .claude/settings.json): hook bị giết
# là mất TOÀN BỘ status đầu phiên, không riêng phần chậm.
def run_quiet(*args: str, timeout: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            [sys.executable, *args],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None


# Sức khoẻ cron job — đo độ tươi từ DB + LastTaskResult (ADR-0013), không đọc dòng cuối log:
# job bị giết giữa chừng không ghi dòng nào, dòng cuối cũ trông như "OK".
health = run_quiet("-m", "scripts.job_health", timeout=10)
if health is None or health.returncode != 0:
    lines.append("- Job health check timed out/failed — run `python -m scripts.job_health`")
else:
    for job_line in health.stdout.strip().splitlines():
        note = "  → tell Thy before trusting fresh data" if job_line.startswith("WARN") else ""
        lines.append(f"- Job: {job_line}{note}")

# Cảnh sát nhất quán — chỉ đếm (nhanh, không chạy pytest); chi tiết qua /decision-sweep
checker = run_quiet("-m", "scripts.consistency.check", "--all", "--count", timeout=6)
count = checker.stdout.strip() if checker else ""
if count.isdigit():
    note = " → run `/decision-sweep` before new work" if count != "0" else ""
    lines.append(f"- Consistency violations (docs/decisions/invariants.toml): {count}{note}")
else:
    lines.append("- Consistency count unavailable — run `python -m scripts.consistency.check`")

print("\n".join(lines[:30]))
