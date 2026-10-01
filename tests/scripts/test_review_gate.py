"""Test cổng review tầng 2 (`scripts/review_gate.py`, ADR-0015).

Mỗi test dựng 1 repo git giả trong `tmp_path` — không đụng repo thật. Các test end-to-end
chạy `git commit` THẬT với git hook pre-commit gọi `review_gate.py check`: đó là chỗ duy
nhất thấy index cuối cùng (lệnh ghép `git add && git commit`, `commit -a`, `git -C`).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import review_gate as rg

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "review_gate.py"


def git(root: Path, *args: str, claude: bool = False) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "GIT_INDEX_FILE")}
    if claude:
        env["CLAUDECODE"] = "1"
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "src/a.py", "x = 1\n")
    write(root, "README.md", "# r\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    exe = Path(sys.executable).as_posix()
    (hooks / "pre-commit").write_text(
        f'#!/bin/sh\nexec "{exe}" "{GATE.as_posix()}" check\n', encoding="utf-8", newline="\n"
    )
    (hooks / "pre-commit").chmod(0o755)
    git(root, "config", "core.hooksPath", hooks.as_posix())
    return root


def transcript(
    tmp: Path, prompt: str = "Review the diff", saw_diff: bool = True, command: str | None = None
) -> Path:
    if command is None:
        command = "git status --short && git diff" if saw_diff else "echo OK"
    lines = [
        {"type": "user", "message": {"role": "user", "content": prompt}},
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]
            },
        },
    ]
    path = tmp / f"t{len(list(tmp.glob('t*.jsonl')))}.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return path


def review(
    root: Path, agent: str = rg.REVIEWER, prompt: str = "Review", diff: bool = True
) -> dict[str, set[str]]:
    rg.record_start(root, "a1")
    return rg.record_stop(root, "a1", agent, transcript(root.parent, prompt, diff))


# --- phạm vi --------------------------------------------------------------------------


def test_scope() -> None:
    for logic in (
        "src/pipeline/job_log.py",
        "src/dashboard/src/components/X.tsx",
        "src/dashboard/package.json",
        "src/dashboard/next.config.ts",
        "scripts/consistency/check.py",
        ".claude/hooks/guard_commit.py",
        ".claude/settings.json",
        ".claude/agents/code-reviewer.md",
        "docs/decisions/invariants.toml",
    ):
        assert rg.needs(logic) == [rg.REVIEWER], logic
    assert rg.needs("docs/decisions/0015-x.md") == [rg.AUDITOR]
    for free in (
        "tests/x.py",
        "docs/status.md",
        "README.md",
        "docs/decisions/0000-template.md",
        ".claude/skills/checkpoint/SKILL.md",
        "uv.lock",
        "src/dashboard/public/brand/logo.svg",
    ):
        assert rg.needs(free) == [], free


# --- ghi dấu --------------------------------------------------------------------------


def test_edit_after_review_invalidates_stamp(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    review(repo)
    git(repo, "add", "src/a.py")
    assert rg.missing_reviews(repo) == {}
    write(repo, "src/a.py", "x = 3\n")
    git(repo, "add", "src/a.py")
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/a.py"]}


def test_file_changed_during_review_is_not_stamped(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    rg.record_start(repo, "a1")
    write(repo, "src/a.py", "x = 3\n")  # sửa trong lúc agent đang review
    approved = rg.record_stop(repo, "a1", rg.REVIEWER, transcript(repo.parent))
    assert approved == {}


def test_no_stamp_without_evidence_of_reading_the_diff(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    assert review(repo, diff=False) == {}  # agent không chạy git diff/status nào
    rg.record_start(repo, "a2")
    assert rg.record_stop(repo, "a2", rg.REVIEWER, None) == {}  # không có transcript
    log = (rg.state_dir(repo) / "log.txt").read_text(encoding="utf-8")
    assert "no stamp" in log


def test_auditor_stamps_only_the_adr_it_was_asked_about(repo: Path) -> None:
    write(repo, "docs/decisions/0015-x.md", "# ADR 15\n")
    write(repo, "docs/decisions/0016-y.md", "# ADR 16\n")
    write(repo, "src/a.py", "x = 2\n")
    approved = review(repo, rg.AUDITOR, prompt="Audit the repo against ADR-0015")
    assert set(approved) == {"docs/decisions/0015-x.md"}  # không 0016, không file logic
    approved = review(repo, rg.REVIEWER)
    assert set(approved) == {"src/a.py"}  # reviewer không đóng dấu ADR


def test_rename_counts_the_deleted_old_path(repo: Path) -> None:
    (repo / "tests").mkdir()
    assert git(repo, "mv", "src/a.py", "tests/a.py").returncode == 0
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/a.py"]}
    review(repo)
    assert rg.missing_reviews(repo) == {}


def test_deleting_a_reviewed_new_file_needs_its_own_review(repo: Path) -> None:
    write(repo, "src/n.py", "y = 1\n")
    review(repo)  # dấu cho file mới — không được kèm DELETED
    git(repo, "add", "src/n.py")
    git(repo, "commit", "-q", "-m", "add n")  # không có CLAUDECODE → cổng bỏ qua
    git(repo, "rm", "-q", "src/n.py")
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/n.py"]}


def test_review_in_main_does_not_stamp_other_worktrees(repo: Path) -> None:
    # Phiên khác đang sửa ở worktree khác: review ở checkout chính không được đóng dấu hộ
    wt = repo.parent / "wt"
    git(repo, "worktree", "add", "-q", str(wt))
    write(wt, "src/a.py", "x = 5\n")
    review(repo)
    git(wt, "add", "src/a.py")
    assert rg.missing_reviews(wt) == {rg.REVIEWER: ["src/a.py"]}


def test_review_from_the_worktree_session_stamps_that_worktree(repo: Path) -> None:
    wt = repo.parent / "wt"
    git(repo, "worktree", "add", "-q", str(wt))
    write(wt, "src/a.py", "x = 5\n")
    review(wt)  # hook chạy với cwd = worktree (phiên mở ở worktree đó)
    git(wt, "add", "src/a.py")
    assert rg.missing_reviews(wt) == {}
    assert rg.state_dir(wt) == rg.state_dir(repo)  # dấu dùng chung, khoá theo nội dung


def test_nested_worktree_review_does_not_stamp_the_main_checkout(repo: Path) -> None:
    # `/wt` đặt worktree trong `.claude/worktrees/` — bên trong checkout chính. Bản so chuỗi
    # con đường dẫn từng đóng dấu nhầm thay đổi của checkout chính (code-reviewer vòng 3).
    write(repo, ".gitignore", ".claude/worktrees/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore worktrees")
    wt = repo / ".claude" / "worktrees" / "feat"
    git(repo, "worktree", "add", "-q", str(wt))
    write(repo, "src/a.py", "x = 7\n")  # thay đổi của phiên khác ở checkout chính
    write(wt, "src/b.py", "y = 1\n")
    rg.record_start(wt, "a1")
    command = f'git -C "{wt.as_posix()}" diff && git status'
    rg.record_stop(wt, "a1", rg.REVIEWER, transcript(repo.parent, command=command))
    git(repo, "add", "src/a.py")
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/a.py"]}
    git(wt, "add", "src/b.py")
    assert rg.missing_reviews(wt) == {}


def test_staged_older_version_is_not_stamped_by_a_review_of_the_disk(repo: Path) -> None:
    # Stage bản lỗi, sửa trên đĩa nhưng chưa add, reviewer đọc bản đĩa → commit bản index bị chặn
    write(repo, "src/a.py", "x = 2  # bug\n")
    git(repo, "add", "src/a.py")
    write(repo, "src/a.py", "x = 3  # fixed\n")
    review(repo)
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/a.py"]}
    git(repo, "add", "src/a.py")
    assert rg.missing_reviews(repo) == {}


def test_auditor_needs_an_explicit_adr_reference(repo: Path) -> None:
    write(repo, "docs/decisions/0015-x.md", "# ADR 15\n")
    assert review(repo, rg.AUDITOR, prompt="check commit 3a0015f and run 0015 tests") == {}
    approved = review(repo, rg.AUDITOR, prompt="Audit against docs/decisions/0015-x.md")
    assert set(approved) == {"docs/decisions/0015-x.md"}


def test_stamps_for_committed_content_are_pruned(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    review(repo)
    git(repo, "add", "src/a.py")
    git(repo, "commit", "-q", "-m", "a")
    write(repo, "src/b.py", "y = 1\n")
    review(repo)  # lượt sau dọn dấu của blob không còn ở đâu ngoài HEAD
    stamps = rg.load_stamps(repo)[rg.REVIEWER]
    assert set(stamps) == {"src/b.py"}


def test_lock_steals_only_stale_locks(tmp_path: Path) -> None:
    lock = tmp_path / "stamps.lock"
    lock.write_text("other-live-process", encoding="utf-8")
    old = 100.0
    os.utime(lock, (old, old))  # khoá mồ côi rất cũ → được cướp
    with rg._Lock(lock):
        assert lock.read_text() != "other-live-process"
    assert not lock.exists()
    lock.write_text("someone-else", encoding="utf-8")
    holder = rg._Lock(lock)
    holder.__exit__()  # không phải khoá của mình → không xoá
    assert lock.read_text() == "someone-else"


def test_stamps_live_in_git_dir_not_worktree(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    review(repo)
    assert (repo / ".git" / "claude-review" / "stamps.json").is_file()
    assert "claude-review" not in git(repo, "status", "--porcelain").stdout


def test_main_ignores_other_agents_and_sanitises_ids(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(repo, "src/a.py", "x = 2\n")
    t = transcript(repo.parent)
    for agent_type, agent_id in (("Explore", "z9"), (rg.REVIEWER, "../x1")):
        for event in ("start", "stop"):
            payload = {
                "agent_type": agent_type,
                "agent_id": agent_id,
                "cwd": str(repo),
                "agent_transcript_path": str(t),
            }
            monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
            assert rg.main([event]) == 0
    assert set(rg.load_stamps(repo)) == {rg.REVIEWER}
    assert not list(rg.state_dir(repo).glob("start-*"))


def test_merge_with_conflict_only_needs_review_of_the_resolution(repo: Path) -> None:
    # Nội dung y nguyên bản ở MERGE_HEAD đã qua cổng trên nhánh kia → không bắt review lại
    git(repo, "checkout", "-q", "-b", "other")
    write(repo, "src/b.py", "y = 1\n")
    write(repo, "README.md", "# other\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "other")
    git(repo, "checkout", "-q", "-")
    write(repo, "README.md", "# main\n")
    write(repo, "src/a.py", "x = 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "main")
    assert git(repo, "merge", "other").returncode != 0  # xung đột README
    write(repo, "README.md", "# merged\n")
    git(repo, "add", "README.md")
    assert rg.missing_reviews(repo) == {}  # src/b.py lấy nguyên từ nhánh other
    write(repo, "src/b.py", "y = 2  # sửa trong lúc merge\n")
    git(repo, "add", "src/b.py")
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/b.py"]}


def test_deleting_our_own_file_during_a_merge_still_needs_review(repo: Path) -> None:
    # File nhánh kia chưa từng có (không ở merge-base, không ở MERGE_HEAD) mà mình xoá lúc
    # merge → không phải "lấy từ nhánh kia" → vẫn cần review (code-reviewer vòng 5)
    git(repo, "checkout", "-q", "-b", "other")
    write(repo, "README.md", "# other\n")
    git(repo, "commit", "-qam", "other")
    git(repo, "checkout", "-q", "-")
    write(repo, "src/ours_only.py", "z = 1\n")
    write(repo, "README.md", "# main\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "main")
    assert git(repo, "merge", "other").returncode != 0
    write(repo, "README.md", "# merged\n")
    git(repo, "add", "README.md")
    git(repo, "rm", "-q", "src/ours_only.py")
    assert rg.missing_reviews(repo) == {rg.REVIEWER: ["src/ours_only.py"]}


def test_deletion_made_on_the_merged_branch_needs_no_review(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "other")
    git(repo, "rm", "-q", "src/a.py")
    write(repo, "README.md", "# other\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "drop a")
    git(repo, "checkout", "-q", "-")
    write(repo, "README.md", "# main\n")
    git(repo, "commit", "-qam", "main")
    assert git(repo, "merge", "other").returncode != 0
    write(repo, "README.md", "# merged\n")
    git(repo, "add", "README.md")
    assert rg.missing_reviews(repo) == {}  # src/a.py đã bị xoá (và review) trên nhánh other


def test_unrelated_histories_merge_does_not_crash(repo: Path) -> None:
    other = repo.parent / "other"
    other.mkdir()
    git(other, "init", "-q")
    write(other, "README.md", "# unrelated\n")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "o")
    git(repo, "fetch", "-q", str(other), "HEAD")
    merged = git(repo, "merge", "--allow-unrelated-histories", "FETCH_HEAD")
    assert merged.returncode != 0  # xung đột README
    write(repo, "README.md", "# both\n")
    git(repo, "add", "README.md")
    assert rg.missing_reviews(repo) == {}  # không có merge-base → không crash, fail-closed vẫn đúng


def test_prunable_and_broken_worktrees_do_not_break_stamping(repo: Path) -> None:
    import shutil

    gone = repo.parent / "gone"
    git(repo, "worktree", "add", "-q", str(gone))
    shutil.rmtree(gone)  # worktree prunable
    broken = repo.parent / "broken"
    git(repo, "worktree", "add", "-q", str(broken))
    (broken / ".git").unlink()  # thư mục còn, liên kết git mất
    assert gone not in rg.worktrees(repo)
    write(repo, "src/a.py", "x = 2\n")
    assert set(review(repo)) == {"src/a.py"}


def test_orphan_start_files_are_cleaned(repo: Path) -> None:
    d = rg.state_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    orphan = d / "start-old.json"
    orphan.write_text("{}", encoding="utf-8")
    os.utime(orphan, (1.0, 1.0))
    rg.record_start(repo, "new")
    assert not orphan.exists()
    assert (d / "start-new.json").exists()


# --- end-to-end: git commit thật qua git hook pre-commit -------------------------------


def test_commit_blocked_until_reviewed(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    git(repo, "add", "src/a.py")
    blocked = git(repo, "commit", "-m", "change", claude=True)
    assert blocked.returncode != 0
    assert "code-reviewer has not reviewed: src/a.py" in blocked.stdout + blocked.stderr
    review(repo)
    assert git(repo, "commit", "-q", "-m", "change", claude=True).returncode == 0


def test_add_then_commit_sees_final_index(repo: Path) -> None:
    # Lỗ hổng của bản PreToolUse: `git add -A && git commit` — giờ cổng chạy SAU `git add`
    write(repo, "src/a.py", "x = 2\n")
    review(repo)
    write(repo, "src/new.py", "z = 1\n")  # chưa review
    git(repo, "add", "-A")
    blocked = git(repo, "commit", "-m", "x", claude=True)
    assert blocked.returncode != 0 and "src/new.py" in blocked.stdout + blocked.stderr


def test_commit_all_checks_the_temporary_index(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    git(repo, "add", "src/a.py")
    review(repo)
    write(repo, "src/a.py", "x = 3\n")  # chưa stage, chưa review — `-a` đưa vào commit
    blocked = git(repo, "commit", "-a", "-m", "x", claude=True)
    assert blocked.returncode != 0
    assert git(repo, "commit", "-q", "-m", "x", claude=True).returncode == 0  # chỉ bản đã stage


def test_manual_commit_by_thy_is_not_gated(repo: Path) -> None:
    write(repo, "src/a.py", "x = 2\n")
    git(repo, "add", "src/a.py")
    assert git(repo, "commit", "-q", "-m", "manual").returncode == 0


def test_docs_and_tests_commit_without_review(repo: Path) -> None:
    write(repo, "README.md", "# changed\n")
    write(repo, "tests/test_x.py", "def test_x() -> None: ...\n")
    git(repo, "add", "-A")
    assert git(repo, "commit", "-q", "-m", "docs", claude=True).returncode == 0


def test_initial_commit_without_head_is_gated(tmp_path: Path) -> None:
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "src/a.py", "x = 1\n")
    git(root, "add", "-A")
    assert rg.missing_reviews(root) == {rg.REVIEWER: ["src/a.py"]}


def test_check_fails_closed_outside_a_repo(tmp_path: Path) -> None:
    env = {**os.environ, "CLAUDECODE": "1"}
    result = subprocess.run(
        [sys.executable, str(GATE), "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 1 and "failed" in result.stdout


# --- đường lách cổng (hook PreToolUse guard_commit.py) ---------------------------------


GUARD = REPO_ROOT / ".claude" / "hooks" / "guard_commit.py"


def guard(command: str) -> int:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True
    ).returncode


@pytest.mark.parametrize(
    "command",
    [
        'SKIP=review-gate git commit -m "x"',
        'CLAUDECODE= git commit -m "x"',
        'env -u CLAUDECODE git commit -m "x"',
        'git -c core.hooksPath=/tmp/none commit -m "x"',
        'git -c "core.hooksPath=/dev/null" commit -m "x"',
        "bash -c 'SKIP=review-gate git commit -m x'",
        'git add -A\nSKIP=review-gate git commit -m "x"',
        'git commit --no-verify -m "x"',
        'git commit --no-verify -m "x" 2>&1 | tail -n 20',
        # vòng 5: redirect trước cờ, -n gộp, dòng mở heredoc, PowerShell `$env:SKIP = …`
        'git commit -m "x" 2>&1 --no-verify',
        "git commit &>/dev/null --no-verify -m x",
        'git commit -nm "x"',
        'git commit -qn -m "x"',
        "cat <<'EOF' | SKIP=review-gate git commit -F -\nTitle\nEOF",
        "git commit -F - <<'EOF' --no-verify\nTitle\nEOF",
        "$env:SKIP = 'review-gate'; git commit -m 'x'",
        # vòng 6: dòng tiếp diễn, lệnh commit thứ 2, --no-verify viết tắt
        "git commit -m x \\\n  --no-verify",
        "git commit \\\n  -n -m x",
        "git commit -m x `\n  --no-verify",
        "git -C repo \\\n  commit -n -m x",
        "git commit -m x || git commit --no-verify -m x",
        "git commit --no-veri -m x",
    ],
)
def test_guard_blocks_gate_bypasses(command: str) -> None:
    assert guard(command) == 2


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "explain why SKIP= and CLAUDECODE matter"',
        "git commit -q -F - <<'EOF'\nTitle\n\n- gate runs when CLAUDECODE=1; SKIP= blocked\nEOF",
        "git status",
        'grep -rn "git commit" docs',
        "git show HEAD:.pre-commit-config.yaml | grep -n CLAUDECODE",
        "git config --get core.hooksPath; ls .git/hooks/pre-commit",
        "git diff -- .pre-commit-config.yaml && grep -n SKIP= .claude/hooks/guard_commit.py",
        # vòng 4: pipe / & / nhiều dòng sau commit không phải `-n` (--no-verify)
        'git commit -m "x" 2>&1 | tail -n 20',
        "git commit -q -F - <<'EOF' 2>&1 | head -n 40\nTitle\nEOF",
        'git commit -m "x"\ngit log -n 1',
        'git commit -m "x" & git log -n 1',
        # vòng 4: message nhắc tới tên biến, cờ gộp, here-string PowerShell, lệnh sau commit
        'git commit -am "gate only runs when CLAUDECODE=1"',
        'git commit -qm "document SKIP= handling"',
        "git commit -m @'\nTitle\n\ngate runs when CLAUDECODE=1\n'@",
        "@'\nTitle about hooksPath\n'@ | git commit -F -",
        "git commit -m x && git log -1 --format=%B | grep CLAUDECODE",
        'git -C "C:/a b/repo" commit -m "x"',
        'git commit -m"gate runs when CLAUDECODE=1"',
        "git commit -F - <<'EOF'\nTitle\n\nEOF handling: gate runs when CLAUDECODE=1\nEOF",
        "git commit -m wip; echo CLAUDECODE",
        "git commit --no-verbose -m x",
    ],
)
def test_guard_allows_normal_commands(command: str) -> None:
    assert guard(command) == 0


def test_guard_sees_git_dash_c_with_a_quoted_path() -> None:
    assert guard('git -C "C:/a b/repo" commit --no-verify -m "x"') == 2


def test_guard_is_wired_for_env_shell_and_powershell_commands() -> None:
    # Test gọi thẳng guard_commit.py nên KHÔNG đi qua bộ lọc `if` của Claude Code; kiểm cấu
    # hình để lệnh bắt đầu bằng env/bash/sh và tool PowerShell thật sự tới được guard.
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    guarded = [
        (e["matcher"], h.get("if"))
        for e in entries
        for h in e["hooks"]
        if "guard_commit.py" in h["command"]
    ]
    assert {("Bash", f"Bash({c} *)") for c in ("git", "env", "bash", "sh")} <= set(guarded)
    assert ("PowerShell", None) in guarded


def test_tests_are_isolated_from_git_hook_env(tmp_path: Path) -> None:
    # Hồi quy: pytest chạy trong git hook (commit -a) nhận GIT_INDEX_FILE tuyệt đối của repo
    # thật; conftest phải xoá nó, nếu không test repo tạm ghi đè index thật.
    decoy = tmp_path / "decoy-index"
    decoy.write_bytes(b"untouched")
    env = {**os.environ, "GIT_INDEX_FILE": str(decoy)}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"{Path(__file__).as_posix()}::test_commit_blocked_until_reviewed",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-500:]
    assert decoy.read_bytes() == b"untouched"
