"""Nhắc quy ước git (ADR-0019) — hook đầu phiên gọi: `python -m scripts.git_hygiene [repo]`.

Quy ước: **thư mục chính** (checkout gốc, nơi 2 cron chạy — ADR-0013/0017) luôn đứng ở `main`;
mọi thay đổi làm trong **worktree** trên nhánh riêng → PR → CI → merge commit. Script chỉ ĐỌC
(`git --no-optional-locks`: không lấy `index.lock`, không chặn commit của phiên/tool khác) và in
cảnh báo. Chi tiết: `docs/claude/git-workflow.md`.

Kiểm tra (in TỪNG dòng ngay khi có — bị giết giữa chừng vẫn giữ được phần đã in):
1. Thư mục chính không ở `main` → cron chạy code của nhánh khác (chưa qua PR/CI).
2. Thư mục chính có thay đổi CHƯA COMMIT ở code cron import → lần chạy kế tiếp dùng bản sửa dở
   (sự cố 2026-10-04: job snapshot migrate DB thật bằng bản nháp ADR-0018).
3. `main` local lệch `origin/main` (theo lần fetch gần nhất): đi trước = có commit thẳng lên
   main; đi sau = PR đã merge nhưng thư mục chính chưa pull → cron chạy code cũ.
4. Nhánh có commit chưa vào `main` → nhắc mở PR (liệt kê, không ngưỡng).
5. Worktree có thay đổi chưa commit → việc dở.

Không bao giờ crash: hook đầu phiên phụ thuộc vào output này.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

MAIN_BRANCH = "main"
UPSTREAM = f"origin/{MAIN_BRANCH}"
# Module mà 2 cron import (đồ thị import của `src.pipeline.scheduled_job` + `nlp_cluster_job` —
# test `test_cron_code_covers_the_cron_import_graph` giữ danh sách này đúng). `src/analysis/` thuộc
# cron từ ADR-0023: bước `compare` của job NLP (`src.pipeline.compare_topics`) chạy engine thống kê.
CRON_CODE_PREFIXES = (
    "src/pipeline/",
    "src/analysis/",
    "src/db/",
    "src/nlp/",
    "src/api/",
    "src/processing/",
    "src/models/",
)
# Package gốc + môi trường: cron chạy thẳng `.venv\Scripts\pythonw.exe` (không `uv sync`) — đổi
# pyproject/uv.lock ở đây mà chưa sync thì lần chạy kế tiếp lệch môi trường.
CRON_CODE_FILES = ("src/__init__.py", "pyproject.toml", "uv.lock")
# Hook đầu phiên cho script này 3s (session_status.py), tính từ lúc tạo tiến trình → đồng hồ chạy
# từ lúc import module (không phải lúc tạo `Git`) và chừa ~0,5s cho khởi động Python/uv.
DEADLINE_S = 2.5
_T0 = time.monotonic()
INCOMPLETE = "Kiểm tra git chưa xong (hết giờ) — chạy `uv run python -m scripts.git_hygiene`"


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str | None  # None = detached HEAD
    prunable: bool


class Git:
    """Gọi git chỉ-đọc với hạn chót chung. Hết giờ → trả chuỗi rỗng, không gọi thêm, và đánh dấu
    `incomplete` — kết quả rỗng vì hết giờ KHÔNG được trông như "không có gì để báo"."""

    def __init__(self, deadline_s: float = DEADLINE_S, start: float | None = None) -> None:
        self.until = (_T0 if start is None else start) + deadline_s
        self.incomplete = False

    def __call__(self, repo: Path, *args: str) -> str:
        left = self.until - time.monotonic()
        if left <= 0:
            self.incomplete = True
            return ""
        try:
            result = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(repo), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=left,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.incomplete = True
            return ""
        except OSError:
            return ""
        return result.stdout if result.returncode == 0 else ""


def parse_worktrees(porcelain: str) -> list[Worktree]:
    """`git worktree list --porcelain` → danh sách; mục đầu tiên luôn là thư mục chính."""
    out: list[Worktree] = []
    for block in porcelain.strip().split("\n\n"):
        fields = [line.split(" ", 1) for line in block.splitlines() if line]
        info = {f[0]: (f[1] if len(f) > 1 else "") for f in fields}
        if "worktree" not in info:
            continue
        ref = info.get("branch", "")
        out.append(
            Worktree(
                path=Path(info["worktree"]),
                branch=ref.removeprefix("refs/heads/") if ref else None,
                prunable="prunable" in info,
            )
        )
    return out


def touches_cron_code(porcelain_status: str) -> list[str]:
    """Đường dẫn chưa commit (từ `git status --porcelain`) thuộc code cron chạy. Thư mục mới
    chưa track hiện dạng `?? src/nlp/new/` — vẫn khớp tiền tố."""
    paths = []
    for line in porcelain_status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip('"')
        if path.startswith(CRON_CODE_PREFIXES) or path in CRON_CODE_FILES:
            paths.append(path)
    return paths


def parse_ahead_behind(for_each_ref: str) -> list[tuple[str, int]]:
    """`for-each-ref --format='%(refname:short) %(ahead-behind:<base>)'` → [(nhánh, ahead > 0)]."""
    rows = []
    for line in for_each_ref.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1].isdigit() and parts[0] != MAIN_BRANCH and int(parts[1]):
            rows.append((parts[0], int(parts[1])))
    return sorted(rows, key=lambda r: -r[1])


def unmerged_branches(git: Git, repo: Path) -> list[tuple[str, int]]:
    """[(nhánh, số commit chưa có trên main)] — 1 lệnh git cho mọi nhánh (cần git ≥ 2.41; git cũ:
    bỏ qua). So với `origin/main` nếu có (PR merge trên GitHub là đủ, chưa cần pull), không thì
    `main` local."""
    base = next(
        (
            ref
            for ref in (UPSTREAM, MAIN_BRANCH)
            if git(repo, "rev-parse", "--verify", "--quiet", ref)
        ),
        None,
    )
    if base is None:
        return []
    return parse_ahead_behind(
        git(repo, "for-each-ref", f"--format=%(refname:short) %(ahead-behind:{base})", "refs/heads")
    )


def check(repo: Path, emit: Callable[[str], None], git: Git | None = None) -> None:
    git = git or Git(start=time.monotonic())  # gọi như hàm: tính giờ từ lúc gọi
    worktrees = parse_worktrees(git(repo, "worktree", "list", "--porcelain"))
    if not worktrees:
        if git.incomplete:
            emit(INCOMPLETE)
        return
    main_tree = worktrees[0]
    if main_tree.branch != MAIN_BRANCH:
        emit(
            f"WARN thư mục chính đang ở `{main_tree.branch or 'detached'}`, không phải "
            f"`{MAIN_BRANCH}` — cron chạy code chưa qua PR/CI (ADR-0019) → merge PR rồi "
            f"chuyển thư mục chính về `{MAIN_BRANCH}` (`/git-flow status`)"
        )
    dirty_cron = touches_cron_code(git(main_tree.path, "status", "--porcelain"))
    if dirty_cron:
        shown = ", ".join(dirty_cron[:3]) + (" …" if len(dirty_cron) > 3 else "")
        emit(
            f"WARN thư mục chính có {len(dirty_cron)} file code cron chưa commit ({shown}) — "
            "lần cron kế tiếp (snapshot xx:15 mỗi 4h, NLP 12:30) chạy bản sửa dở → chuyển "
            "việc sang worktree (`/git-flow start`)"
        )
    counts = git(repo, "rev-list", "--left-right", "--count", f"{UPSTREAM}...{MAIN_BRANCH}").split()
    if len(counts) == 2 and all(c.isdigit() for c in counts):
        behind, ahead = int(counts[0]), int(counts[1])
        if ahead:
            emit(
                f"WARN `{MAIN_BRANCH}` local có {ahead} commit chưa có trên `{UPSTREAM}` — "
                "commit thẳng lên main? (ADR-0019: mọi thay đổi qua PR)"
            )
        if behind:
            emit(
                f"`{MAIN_BRANCH}` local chậm {behind} commit so với `{UPSTREAM}` (lần fetch gần "
                "nhất) → ở thư mục chính: `git pull` + `uv sync --frozen` để cron chạy code mới"
            )
    unmerged = unmerged_branches(git, repo)
    if unmerged:
        listed = ", ".join(f"`{name}` +{n}" for name, n in unmerged[:4])
        emit(f"Nhánh chưa merge vào main: {listed} → `/git-flow finish` khi xong")
    for tree in worktrees[1:]:
        name = tree.branch or "detached"
        if tree.prunable:
            emit(f"Worktree `{name}` mất thư mục: {tree.path} → `git worktree prune`")
        elif git(tree.path, "status", "--porcelain").strip():
            emit(f"Worktree `{name}` có việc dở chưa commit ({tree.path.name})")
    if git.incomplete:
        emit(INCOMPLETE)


def report(repo: Path, git: Git | None = None) -> list[str]:
    lines: list[str] = []
    check(repo, lines.append, git)
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    repo = Path(argv[0]) if argv else Path.cwd()
    try:
        check(repo, lambda line: print(line, flush=True), Git())  # script: tính từ lúc khởi động
    except Exception as exc:  # noqa: BLE001 — hook đầu phiên không bao giờ được crash
        print(f"git hygiene check failed: {exc!r}", flush=True)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
