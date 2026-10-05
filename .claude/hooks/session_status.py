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
    # --no-optional-locks: chỉ đọc, không lấy index.lock → không chặn commit của phiên/tool khác
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(project), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


lines: list[str] = ["## Session status (auto, .claude/hooks/session_status.py)"]

branch = git("branch", "--show-current") or "(detached)"
dirty = [line for line in git("status", "--porcelain").splitlines() if line]
lines.append(f"- Branch: `{branch}` — {len(dirty)} uncommitted file(s)")
if dirty:
    lines.append("  → If the last step is green, propose `/checkpoint`.")
lines.append("- Last commits:")
lines += [f"  - {c}" for c in git("log", "-3", "--format=%h %s (%cr)").splitlines()]

# docs/status.md: "Next" trước (việc cần làm), rồi "Blocked", rồi "Now" — mục "Now" dài nên in
# cuối, cắt bớt nếu hết chỗ
status_md = project / "docs" / "status.md"
if status_md.exists():
    sections: dict[str, list[str]] = {"next": [], "blocked": [], "now": []}
    current: str | None = None
    for line in status_md.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            title = line[3:].strip().lower()
            current = next((key for key in sections if title.startswith(key)), None)
        if current is not None and line.strip():
            sections[current].append(line)
    block = sections["next"][:6] + sections["blocked"][:3]
    block += sections["now"][: max(0, 12 - len(block))]
    if block:
        lines.append("- From docs/status.md:")
        lines += [f"  {line}" for line in block]


# Tổng timeout: 3 lệnh git ở trên (3 × 1s) + subprocess (10 + 3 + 6s) = 22s < timeout của hook
# (25s, .claude/settings.json) — chừa ~3s khởi động uv/Python. Hook bị giết là mất TOÀN BỘ
# status đầu phiên, không riêng phần chậm.
def run_quiet(*args: str, timeout: float) -> tuple[str, bool]:
    """(stdout, xong-bình-thường). Quá giờ: trả phần stdout đã in được + False."""
    try:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        return partial or "", False
    return result.stdout, result.returncode == 0


# Sức khoẻ cron job — đo độ tươi từ DB + LastTaskResult (ADR-0013), không đọc dòng cuối log:
# job bị giết giữa chừng không ghi dòng nào, dòng cuối cũ trông như "OK".
health, health_ok = run_quiet("-m", "scripts.job_health", timeout=10)
if not health_ok:
    lines.append("- Job health check timed out/failed — run `uv run python -m scripts.job_health`")
else:
    for job_line in health.strip().splitlines():
        note = "  → tell Thy before trusting fresh data" if job_line.startswith("WARN") else ""
        lines.append(f"- Job: {job_line}{note}")

# Quy ước git (ADR-0019): thư mục chính ở main, mọi thay đổi trong worktree, nhánh → PR. Script
# in từng dòng ngay khi có → quá giờ vẫn giữ các cảnh báo đã tính xong.
hygiene, hygiene_ok = run_quiet("-m", "scripts.git_hygiene", str(project), timeout=3)
git_lines = hygiene.strip().splitlines()
lines += [f"- Git: {line}" for line in git_lines[:5]]
if len(git_lines) > 5:
    lines.append(f"- Git: +{len(git_lines) - 5} dòng nữa — `uv run python -m scripts.git_hygiene`")
if not hygiene_ok:
    lines.append(
        "- Git hygiene check timed out/failed — run `uv run python -m scripts.git_hygiene`"
    )

# Cảnh sát nhất quán — chỉ đếm (nhanh, không chạy pytest); chi tiết qua /decision-sweep
checker, _ = run_quiet("-m", "scripts.consistency.check", "--all", "--count", timeout=6)
count = checker.strip()
if count.isdigit():
    note = " → run `/decision-sweep` before new work" if count != "0" else ""
    lines.append(f"- Consistency violations (docs/decisions/invariants.toml): {count}{note}")
else:
    lines.append(
        "- Consistency count unavailable — run `uv run python -m scripts.consistency.check`"
    )

print("\n".join(lines[:30]))
