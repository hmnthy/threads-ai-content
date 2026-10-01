"""Cổng review tầng 2 (ADR-0015): commit do Claude chạy, chạm logic, phải có dấu review khớp
ĐÚNG nội dung (blob hash của git).

- `start` / `stop` — hook `SubagentStart` / `SubagentStop` (matcher
  `code-reviewer|consistency-auditor`, JSON của hook qua stdin): chụp blob TRÊN ĐĨA của các
  file trong phạm vi đang khác HEAD ở worktree của phiên (cwd của hook), lúc agent bắt đầu và
  kết thúc. Ghi dấu cho blob không đổi suốt lượt — và chỉ khi transcript cho thấy agent thật
  sự đã chạy lệnh xem diff. Review worktree khác → chạy agent từ phiên của worktree đó (không
  đoán worktree từ đường dẫn trong lệnh: worktree của `/wt` nằm trong checkout chính, so
  chuỗi con từng đóng dấu nhầm — code-reviewer 2026-10-01).
- `check` — git hook pre-commit (`.pre-commit-config.yaml`), chỉ chạy khi `CLAUDECODE=1`
  (shell của Claude Code): lúc này git đã dựng xong index cuối cùng (kể cả `commit -a`,
  pathspec, lệnh ghép `git add … && git commit`) và đang đứng đúng repo/worktree. Thy commit
  tay (không có biến này) không bị ảnh hưởng.

Vì sao không đặt ở hook PreToolUse: hook đó chạy TRƯỚC lệnh Bash → thấy index cũ khi lệnh là
`git add -A && git commit`, nhầm repo khi `git -C <dir> commit`, và khớp nhầm mọi lệnh chỉ
chứa chữ "git commit" (code-reviewer tái hiện cả 3, 2026-10-01).

Dấu lưu ở `<git-common-dir>/claude-review/` — dùng chung mọi worktree (khoá theo nội dung
nên an toàn), không bao giờ vào commit. Lỗi git → chặn (fail closed). Chỉ thư viện chuẩn.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REVIEWER = "code-reviewer"
AUDITOR = "consistency-auditor"
DELETED = "<deleted>"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # cây rỗng của git (repo chưa có commit)
LOCK_TIMEOUT_S = 10  # khoá stamps.json cũ hơn mức này = tiến trình giữ khoá đã chết
ORPHAN_START_S = 24 * 3600  # file start-*.json bị bỏ lại (SubagentStop không bắn)
LOG_KEEP = 500  # số dòng log.txt giữ lại

# File "logic" — đổi hành vi / số liệu / luật / chính cổng này → phải qua code-reviewer.
# Không gồm: tests/ (qa-tester), docs, skills/rules (chỉ dẫn văn bản), ảnh/svg, lockfile (máy sinh).
REVIEW_SCOPE = (
    "src/*.py",
    "src/dashboard/src/*.ts",
    "src/dashboard/src/*.tsx",
    "src/dashboard/src/*.js",
    "src/dashboard/src/*.mjs",
    "src/dashboard/src/*.css",
    "src/dashboard/scripts/*",
    "src/dashboard/package.json",
    "src/dashboard/*.config.*",
    "src/dashboard/tsconfig.json",
    "scripts/*",
    ".claude/hooks/*",
    ".claude/settings.json",
    ".claude/agents/*",
    ".github/workflows/*",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "docs/decisions/invariants.toml",
)
# ADR mới/sửa → phải qua consistency-auditor (kiểm toán độc lập, ADR-0008)
ADR_PATH = re.compile(r"^docs/decisions/(\d{4})-[^/]+\.md$")
# Dấu hiệu tối thiểu agent đã đọc thay đổi: 1 lệnh git xem diff/trạng thái
DIFF_COMMAND = re.compile(r"\bgit\b[^\n]*\b(diff|status|show)\b")


def in_review_scope(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in REVIEW_SCOPE)


def adr_number(path: str) -> str | None:
    m = ADR_PATH.match(path)
    return m.group(1) if m and m.group(1) != "0000" else None


def needs(path: str) -> list[str]:
    out = [REVIEWER] if in_review_scope(path) else []
    if adr_number(path):
        out.append(AUDITOR)
    return out


# --- git -----------------------------------------------------------------------------


class GitError(RuntimeError):
    pass


def _git(root: Path, *args: str, stdin: str | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=off", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=stdin,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])} lỗi: {result.stderr.strip()[:200]}")
    return result.stdout


def _z(out: str) -> list[str]:
    return [p for p in out.split("\0") if p]


def repo_root(start: Path) -> Path:
    return Path(_git(start, "rev-parse", "--show-toplevel").strip())


def head_ref(root: Path) -> str:
    try:
        _git(root, "rev-parse", "--verify", "-q", "HEAD")
    except GitError:
        return EMPTY_TREE
    return "HEAD"


def head_blobs(root: Path) -> dict[str, str]:
    ref = head_ref(root)
    if ref == EMPTY_TREE:
        return {}
    out: dict[str, str] = {}
    for entry in _z(_git(root, "ls-tree", "-r", "-z", ref)):
        meta, _, path = entry.partition("\t")
        out[path] = meta.split()[2]
    return out


def index_blobs(root: Path) -> dict[str, str]:
    """Blob trong index (tôn trọng GIT_INDEX_FILE mà git đặt cho hook lúc `commit -a`)."""
    out: dict[str, str] = {}
    for entry in _z(_git(root, "ls-files", "-s", "-z")):
        meta, _, path = entry.partition("\t")
        out[path] = meta.split()[1]
    return out


def worktree_blobs(root: Path, paths: list[str]) -> dict[str, str]:
    existing = [p for p in paths if (root / p).is_file()]
    if not existing:
        return {}
    hashes = _git(root, "hash-object", "--stdin-paths", stdin="\n".join(existing) + "\n").split()
    return dict(zip(existing, hashes, strict=True))


def changed_paths(root: Path) -> list[str]:
    """Path khác HEAD: trên đĩa, trong index, file mới chưa track. `--no-renames`: đổi tên =
    xoá path cũ + thêm path mới — path cũ bị xoá cũng phải được review."""
    ref = head_ref(root)
    paths = set(_z(_git(root, "diff", "--name-only", "--no-renames", "-z", ref)))
    paths |= set(_z(_git(root, "diff", "--cached", "--name-only", "--no-renames", "-z", ref)))
    paths |= set(_z(_git(root, "ls-files", "--others", "--exclude-standard", "-z")))
    return sorted(paths)


def worktrees(root: Path) -> list[Path]:
    """Worktree còn dùng được (bỏ entry `prunable` — thư mục đã xoá / hỏng)."""
    out: list[Path] = []
    for block in _git(root, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.splitlines()
        if (
            lines
            and lines[0].startswith("worktree ")
            and not any(line.startswith("prunable") for line in lines)
        ):
            out.append(Path(lines[0][9:]))
    return out


def state_dir(root: Path) -> Path:
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common / "claude-review"


# --- snapshot -------------------------------------------------------------------------


def snapshot(root: Path) -> dict[str, str]:
    """path → blob TRÊN ĐĨA (bản agent đọc được) của file cần review đang khác HEAD, 1 worktree.

    Không lấy bản trong index: reviewer đọc file trên đĩa; nếu index giữ bản cũ hơn thì bản
    đó chưa được review (code-reviewer 2026-10-01). File đã xoá → DELETED, chỉ khi có trong HEAD.
    """
    paths = [p for p in changed_paths(root) if needs(p)]
    head, disk = head_blobs(root), worktree_blobs(root, paths)
    out: dict[str, str] = {}
    for p in paths:
        blob = disk.get(p, DELETED)
        if blob == head.get(p) or (blob == DELETED and p not in head):
            continue
        out[p] = blob
    return out


def stable_blobs(start: dict[str, str], stop: dict[str, str]) -> dict[str, str]:
    return {p: b for p, b in stop.items() if start.get(p) == b}


# --- transcript: agent có thật sự đọc diff? -------------------------------------------


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def transcript_facts(path: Path | None) -> tuple[bool, str]:
    """(đã chạy git diff/status/show?, prompt đầu tiên). Không đọc được → (False, "")."""
    if path is None:
        return False, ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False, ""
    saw_diff, prompt = False, ""
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not prompt and entry.get("type") == "user":
            content = entry.get("message", {}).get("content")
            prompt = (
                content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            )
        for node in _walk(entry.get("message")):
            if node.get("type") == "tool_use" and node.get("name") == "Bash":
                command = str((node.get("input") or {}).get("command", ""))
                if DIFF_COMMAND.search(command):
                    saw_diff = True
    return saw_diff, prompt


def scope_for(agent_type: str, path: str, prompt: str) -> bool:
    """Dấu chỉ cho đúng việc agent được giao: reviewer → file logic; auditor → ADR được nhắc
    rõ trong prompt dạng `ADR-NNNN` / `decisions/NNNN` (không khớp số trần, VD trong hash)."""
    if agent_type == REVIEWER:
        return in_review_scope(path)
    number = adr_number(path)
    if number is None:
        return False
    return re.search(rf"(?:ADR[-\s]?|decisions/){number}(?!\d)", prompt, re.I) is not None


# --- dấu (stamps) ---------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_stamps(root: Path) -> dict[str, dict[str, set[str]]]:
    raw = _read_json(state_dir(root) / "stamps.json")
    stamps: dict[str, dict[str, set[str]]] = {}
    for agent, files in raw.items():
        if isinstance(files, dict):
            stamps[agent] = {
                p: {b for b in blobs if isinstance(b, str)}
                for p, blobs in files.items()
                if isinstance(blobs, list)
            }
    return stamps


class _Lock:
    """Khoá file (O_EXCL, ghi pid) quanh đọc-sửa-ghi stamps.json. Chỉ cướp khoá đã cũ hơn
    LOCK_TIMEOUT_S (tiến trình giữ khoá đã chết); chỉ xoá khoá của chính mình."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.token = f"{os.getpid()}-{time.monotonic_ns()}"

    def __enter__(self) -> None:
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    continue  # vừa được nhả — thử lại ngay
                if age > LOCK_TIMEOUT_S:
                    self.path.unlink(missing_ok=True)
                else:
                    time.sleep(0.05)
                continue
            with os.fdopen(fd, "w") as f:
                f.write(self.token)
            return

    def __exit__(self, *exc: object) -> None:
        try:
            if self.path.read_text() == self.token:
                self.path.unlink()
        except OSError:
            pass


def _replace(tmp: Path, target: Path) -> None:
    """os.replace có thử lại: Windows báo PermissionError khi `check` đang mở file đích."""
    for attempt in range(20):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def record_start(root: Path, agent_id: str) -> None:
    d = state_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("start-*.json"):  # SubagentStop không bắn (lượt bị ngắt) → dọn sau 1 ngày
        try:
            if time.time() - old.stat().st_mtime > ORPHAN_START_S:
                old.unlink(missing_ok=True)
        except OSError:
            pass  # stop khác vừa xoá — bỏ qua
    (d / f"start-{agent_id}.json").write_text(json.dumps(snapshot(root)), encoding="utf-8")


def record_stop(
    root: Path, agent_id: str, agent_type: str, transcript: Path | None
) -> dict[str, set[str]]:
    """Ghi dấu; trả phần vừa ghi (rỗng nếu agent không chạy lệnh xem diff nào)."""
    d = state_dir(root)
    start_file = d / f"start-{agent_id}.json"
    start_raw = _read_json(start_file)
    start_file.unlink(missing_ok=True)
    saw_diff, prompt = transcript_facts(transcript)
    approved: dict[str, set[str]] = {}
    if saw_diff:
        start_snap = {p: b for p, b in start_raw.items() if isinstance(b, str)}
        for p, b in stable_blobs(start_snap, snapshot(root)).items():
            if scope_for(agent_type, p, prompt):
                approved[p] = {b}
    # Blob còn có thể được commit = đang có trên đĩa hoặc trong index của 1 worktree nào đó;
    # dấu cho blob khác (đã commit xong / đã bị sửa đè) bỏ đi → stamps.json không phình mãi.
    # Worktree hỏng bị bỏ qua (không làm hỏng việc ghi dấu của mọi phiên).
    alive: dict[str, set[str]] = {}
    for wt in worktrees(root):
        try:
            paths = [p for p in changed_paths(wt) if needs(p)]
            disk, index = worktree_blobs(wt, paths), index_blobs(wt)
        except (GitError, OSError):
            continue
        for p in paths:
            alive.setdefault(p, set()).update({disk.get(p, DELETED), index.get(p, DELETED)})
    d.mkdir(parents=True, exist_ok=True)
    with _Lock(d / "stamps.lock"):
        stamps = load_stamps(root)
        stamps.setdefault(agent_type, {})
        for path, blobs in approved.items():
            stamps[agent_type][path] = stamps[agent_type].get(path, set()) | blobs
        pruned = {
            agent: {p: kept for p, bs in files.items() if (kept := bs & alive.get(p, set()))}
            for agent, files in stamps.items()
        }
        tmp = d / f"stamps.{os.getpid()}.tmp"
        tmp.write_text(
            json.dumps(
                {a: {p: sorted(b) for p, b in f.items()} for a, f in pruned.items()}, indent=1
            ),
            encoding="utf-8",
        )
        _replace(tmp, d / "stamps.json")
    log = d / "log.txt"
    note = "" if saw_diff else " (no git diff/status in transcript → no stamp)"
    entry = f"{datetime.now(UTC).isoformat()} {agent_type} {agent_id} {len(approved)} file{note}"
    lines = (log.read_text(encoding="utf-8").splitlines() if log.exists() else [])[-LOG_KEEP:]
    log.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")
    return approved


# --- kiểm tra lúc commit (git hook pre-commit) ----------------------------------------


def merge_head_blobs(root: Path) -> dict[str, str]:
    """Blob ở MERGE_HEAD khi đang merge (rỗng nếu không). Nội dung lấy nguyên từ nhánh kia đã
    qua cổng lúc commit trên nhánh đó — merge có xung đột không bắt review lại toàn bộ."""
    try:
        _git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    except GitError:
        return {}
    return tree_blobs(root, "MERGE_HEAD")


def tree_blobs(root: Path, ref: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in _z(_git(root, "ls-tree", "-r", "-z", ref)):
        meta, _, path = entry.partition("\t")
        out[path] = meta.split()[2]
    return out


def taken_from_merge(path: str, blob: str, merged_in: dict[str, str], base: dict[str, str]) -> bool:
    """Nội dung lấy nguyên từ nhánh được merge: cùng blob ở MERGE_HEAD, hoặc xoá mà nhánh kia
    THẬT SỰ đã xoá (có ở merge-base, không có ở MERGE_HEAD). File nhánh kia chưa từng có mà
    mình xoá trong lúc merge → vẫn phải review (code-reviewer vòng 5)."""
    if blob == DELETED:
        return path in base and path not in merged_in
    return merged_in.get(path) == blob


def missing_reviews(root: Path) -> dict[str, list[str]]:
    """agent → path sắp commit (index vs HEAD) chưa có dấu khớp blob."""
    ref = head_ref(root)
    staged = _z(_git(root, "diff", "--cached", "--name-only", "--no-renames", "-z", ref))
    index = index_blobs(root)
    merged_in = merge_head_blobs(root)
    base: dict[str, str] = {}
    if merged_in:
        try:
            base = tree_blobs(root, _git(root, "merge-base", "HEAD", "MERGE_HEAD").strip())
        except GitError:
            base = {}  # --allow-unrelated-histories: không có merge-base
    stamps = load_stamps(root)
    missing: dict[str, list[str]] = {}
    for path in staged:
        blob = index.get(path, DELETED)
        if merged_in and taken_from_merge(path, blob, merged_in, base):
            continue
        for agent in needs(path):
            if blob not in stamps.get(agent, {}).get(path, set()):
                missing.setdefault(agent, []).append(path)
    return missing


def check(root: Path) -> int:
    if os.environ.get("CLAUDECODE") != "1":
        return 0  # commit tay của Thy — cổng chỉ áp cho Claude
    missing = missing_reviews(root)
    if not missing:
        return 0
    print("review gate (ADR-0015): tier-2 review missing for the exact content being committed.")
    for agent, paths in missing.items():
        shown = ", ".join(paths[:8]) + (f" (+{len(paths) - 8} more)" if len(paths) > 8 else "")
        print(f"- @agent-{agent} has not reviewed: {shown}")
    print(
        "Run the agent on the full diff after the last edit, fix its findings, re-run until "
        "clean, then commit. Any edit after a review invalidates that file's stamp."
    )
    return 1


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if argv[:1] == ["check"]:
        try:
            return check(repo_root(Path.cwd()))
        except GitError as exc:  # fail closed
            print(f"review gate (ADR-0015) failed: {exc}")
            return 1
    if argv[:1] not in (["start"], ["stop"]):
        print("usage: review_gate.py start|stop (hook JSON on stdin) | check")
        return 2
    payload = json.load(sys.stdin)
    agent_type = str(payload.get("agent_type", ""))
    agent_id = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("agent_id", "")))
    if agent_type not in (REVIEWER, AUDITOR) or not agent_id:
        return 0
    root = repo_root(Path(str(payload.get("cwd") or ".")))
    if argv[0] == "start":
        record_start(root, agent_id)
    else:
        raw = payload.get("agent_transcript_path")
        record_stop(root, agent_id, agent_type, Path(str(raw)) if raw else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
