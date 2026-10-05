"""Test nhắc quy ước git (`scripts/git_hygiene.py`, ADR-0019) trên repo git tạm."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path, PureWindowsPath

import pytest

from scripts import git_hygiene as gh
from scripts import job_health
from src.pipeline import nlp_cluster_job

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_FLAG = re.compile(r"-m\s+(src(?:\.\w+)+)")


def cron_entry_modules() -> set[str]:
    """Điểm vào của cron, lấy từ CHÍNH cấu hình: Action trong `configure_jobs.ps1` + mọi bước
    `-m` của job NLP (`build_steps`, kể cả lệnh `python3 -m` chạy trong WSL)."""
    ps1 = (REPO_ROOT / "scripts" / "configure_jobs.ps1").read_text(encoding="utf-8")
    entries = set(MODULE_FLAG.findall(ps1))
    for step in nlp_cluster_job.build_steps(PureWindowsPath("C:/r"), "python"):
        entries |= set(MODULE_FLAG.findall(" ".join(step.argv)))
    return entries


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return out.stdout.decode().strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Không để git leo lên thư mục cha (VD %TEMP% nằm trong 1 repo khác)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src" / "pipeline").mkdir(parents=True)
    (root / "src" / "pipeline" / "job.py").write_text("x = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# r\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_clean_repo_on_main_reports_nothing(repo: Path) -> None:
    assert gh.report(repo) == []


def test_main_checkout_on_another_branch_warns(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / "README.md").write_text("# changed\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "change")
    lines = gh.report(repo)
    assert lines[0].startswith("WARN thư mục chính đang ở `feat/x`")
    assert "`feat/x` +1" in lines[1]


def test_uncommitted_cron_code_in_main_checkout_warns_but_docs_do_not(repo: Path) -> None:
    (repo / "README.md").write_text("# doc edit\n", encoding="utf-8")
    assert gh.report(repo) == []  # sửa docs: cron không chạy
    (repo / "src" / "pipeline" / "job.py").write_text("x = 2\n", encoding="utf-8")
    [line] = gh.report(repo)
    assert line.startswith(
        "WARN thư mục chính có 1 file code cron chưa commit (src/pipeline/job.py)"
    )


def test_new_untracked_cron_directory_is_caught(repo: Path) -> None:
    (repo / "src" / "nlp" / "new").mkdir(parents=True)
    (repo / "src" / "nlp" / "new" / "m.py").write_text("y = 1\n", encoding="utf-8")
    [line] = gh.report(repo)
    assert "src/nlp/" in line


def test_main_ahead_of_or_behind_origin_main(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("# direct\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "direct to main")
    _git(repo, "update-ref", "refs/remotes/origin/main", base)
    assert gh.report(repo)[0].startswith("WARN `main` local có 1 commit chưa có trên `origin/main`")
    # origin/main đi trước (PR đã merge trên GitHub, chưa pull)
    _git(repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD"))
    _git(repo, "reset", "-q", "--hard", base)
    assert gh.report(repo)[0].startswith("`main` local chậm 1 commit so với `origin/main`")


def test_unmerged_branches_are_sorted_by_commits_ahead(repo: Path) -> None:
    for name, commits in (("a", 1), ("b", 3)):
        _git(repo, "checkout", "-q", "-b", name, "main")
        for i in range(commits):
            (repo / f"{name}{i}.txt").write_text("z\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-qm", f"{name}{i}")
    _git(repo, "checkout", "-q", "main")
    assert gh.report(repo) == [
        "Nhánh chưa merge vào main: `b` +3, `a` +1 → `/git-flow finish` khi xong"
    ]


def test_repo_without_main_branch_skips_branch_checks(repo: Path) -> None:
    _git(repo, "branch", "-m", "main", "trunk")
    [line] = gh.report(repo)  # chỉ còn cảnh báo thư mục chính không ở main
    assert line.startswith("WARN thư mục chính đang ở `trunk`")


def test_worktree_with_unfinished_work_is_listed_and_does_not_count_as_main(
    repo: Path, tmp_path: Path
) -> None:
    tree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "chore/y", str(tree))
    (tree / "src" / "pipeline" / "job.py").write_text("x = 3\n", encoding="utf-8")
    lines = gh.report(repo)
    # Sửa code cron TRONG worktree là đúng quy ước → không có WARN về thư mục chính
    assert not any(line.startswith("WARN") for line in lines)
    assert lines == ["Worktree `chore/y` có việc dở chưa commit (wt)"]
    assert gh.report(tree) == lines  # chạy từ worktree cũng nhìn thấy thư mục chính


def test_detached_and_vanished_worktrees_are_rendered(repo: Path, tmp_path: Path) -> None:
    detached = tmp_path / "det"
    _git(repo, "worktree", "add", "-q", "--detach", str(detached))
    (detached / "README.md").write_text("# wip\n", encoding="utf-8")
    gone = tmp_path / "gone"
    _git(repo, "worktree", "add", "-q", "-b", "old", str(gone))
    shutil.rmtree(gone)  # xoá thư mục bằng tay (không qua git) → git đánh dấu prunable
    lines = gh.report(repo)
    assert "Worktree `detached` có việc dở chưa commit (det)" in lines
    assert any(line.startswith("Worktree `old` mất thư mục") for line in lines)


def test_parse_worktrees_handles_detached_prunable_and_spaces() -> None:
    porcelain = (
        "worktree C:/Users/Thy Nguyen/repo\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /r/wt\nHEAD def\ndetached\n\n"
        "worktree /gone\nHEAD 123\nbranch refs/heads/old\nprunable gitdir file points nowhere\n"
    )
    trees = gh.parse_worktrees(porcelain)
    assert trees[0].path == Path("C:/Users/Thy Nguyen/repo")
    assert [(t.branch, t.prunable) for t in trees] == [
        ("main", False),
        (None, False),
        ("old", True),
    ]


def test_touches_cron_code_reads_renames_quotes_and_ignores_scripts() -> None:
    status = (
        " M src/db/schema.py\n"
        'R  old.py -> "src/nlp/tên mới.py"\n'
        " M scripts/x.py\n"
        " M src/analysis/stats.py\n"
        "?? uv.lock\n"
    )
    assert gh.touches_cron_code(status) == ["src/db/schema.py", "src/nlp/tên mới.py", "uv.lock"]


def test_parse_ahead_behind_drops_main_zero_and_garbage() -> None:
    out = "main 0 0\nfeat/a 2 5\nfix/b 0 1\nweird line\nchore/c 7 0\n"
    assert gh.parse_ahead_behind(out) == [("chore/c", 7), ("feat/a", 2)]


def test_expired_deadline_is_reported_not_silent(repo: Path) -> None:
    # Hết giờ → không được trông như "không có gì để báo"
    assert gh.report(repo, gh.Git(deadline_s=0)) == [
        "Kiểm tra git chưa xong (hết giờ) — chạy `uv run python -m scripts.git_hygiene`"
    ]


def test_not_a_repo_reports_nothing_and_main_never_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert gh.report(tmp_path) == []
    assert gh.main([str(tmp_path)]) == 0


def test_job_health_measures_the_main_checkout_from_a_worktree(repo: Path, tmp_path: Path) -> None:
    tree = tmp_path / "wt2"
    _git(repo, "worktree", "add", "-q", "-b", "chore/z", str(tree))
    assert job_health.main_checkout(tree).resolve() == repo.resolve()
    assert job_health.main_checkout(tmp_path / "nowhere") == tmp_path / "nowhere"


def _src_imports(module: str) -> set[str]:
    path = REPO_ROOT / Path(*module.split("."))
    file = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
    found: set[str] = set()
    for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names if a.name.startswith("src.")}
        elif isinstance(node, ast.ImportFrom):
            # Import tương đối sẽ lọt khỏi phép dò này → cấm hẳn trong code cron
            assert node.level == 0, f"relative import in {file}"
            if node.module and (node.module == "src" or node.module.startswith("src.")):
                found.add(node.module)
                found |= {f"{node.module}.{a.name}" for a in node.names}
    return {
        m
        for m in found
        if (REPO_ROOT / Path(*m.split("."))).with_suffix(".py").exists()
        or (REPO_ROOT / Path(*m.split(".")) / "__init__.py").exists()
    }


def test_cron_code_covers_the_cron_import_graph() -> None:
    """Mọi module 2 cron import (đệ quy, kể cả `__init__` của package cha) phải nằm trong
    `CRON_CODE_PREFIXES`/`CRON_CODE_FILES` — thêm module mới mà quên danh sách thì test đỏ."""
    seen: set[str] = set()
    entries = cron_entry_modules()
    assert {"src.pipeline.scheduled_job", "src.pipeline.nlp_cluster_job"} <= entries
    todo = sorted(entries)
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        parts = module.split(".")
        todo += [".".join(parts[:i]) for i in range(1, len(parts)) if parts[:i] != ["src"]]
        todo += sorted(_src_imports(module) - seen)
    files = {"src/__init__.py"}
    for module in seen:
        path = Path(*module.split("."))
        file = path / "__init__.py" if (REPO_ROOT / path).is_dir() else path.with_suffix(".py")
        files.add(file.as_posix())
    uncovered = sorted(
        f for f in files if not (f.startswith(gh.CRON_CODE_PREFIXES) or f in gh.CRON_CODE_FILES)
    )
    assert uncovered == []
    # Mỗi tiền tố thật sự có module cron dùng (không cảnh báo thừa — VD src/analysis/ chỉ API dùng)
    unused = [p for p in gh.CRON_CODE_PREFIXES if not any(f.startswith(p) for f in files)]
    assert unused == []
