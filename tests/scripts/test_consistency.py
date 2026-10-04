"""Test cho cảnh sát nhất quán (`scripts/consistency/check.py`).

Mỗi test dựng 1 repo git giả trong `tmp_path` — không đụng repo thật. Riêng
`test_real_invariants_catch_known_lapses` nạp sổ luật THẬT để bảo đảm 7 kiểu lỗi
thời đã phát hiện ngày 2026-09-30 luôn bị bắt (không ai vô tình nới lỏng luật).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.consistency import check

REPO_ROOT = Path(__file__).resolve().parents[2]

BASE_TOML = """
[settings]
exclude = ["docs/archive/**", "docs/decisions/invariants.toml"]
dead_path_exclude = []
planned_paths = ["src/kb", "src/kb/**"]
known_untracked = ["data/**"]
"""


def _git(root: Path, *args: str, date: str | None = None) -> None:
    env = {**os.environ}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        env=env,
    )


def make_repo(tmp_path: Path, files: dict[str, str], rules: str = "") -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    for rel, content in {**files, check.INVARIANTS_PATH: BASE_TOML + rules}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init", date="2026-01-01T00:00:00")
    return root


def run_forbid(root: Path) -> list[check.Violation]:
    cfg = check.load_config(root)
    return check.check_forbid(root, check.tracked_files(root), cfg)


PHASE_RULE = """
[[forbid]]
id = "R-phase"
adr = "0001"
pattern = '(?i)\\bphase[ ]?[12]\\b'
why = "đã bỏ"
allow = ["docs/decisions/**"]
"""


# --- forbid ---------------------------------------------------------------------------


def test_forbid_reports_file_line_and_rule(tmp_path: Path) -> None:
    root = make_repo(tmp_path, {"README.md": "ok\nStatus: Phase 1\n"}, PHASE_RULE)
    [v] = run_forbid(root)
    assert (v.path, v.line, v.rule, v.adr) == ("README.md", 2, "R-phase", "0001")


def test_forbid_respects_allow_glob_and_global_exclude(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        {"docs/decisions/0001-x.md": "Phase 1 bị bỏ", "docs/archive/old.md": "Phase 2"},
        PHASE_RULE,
    )
    assert run_forbid(root) == []


def test_inline_allow_same_line_and_previous_line(tmp_path: Path) -> None:
    content = (
        "Phase 1 was dropped <!-- consistency: allow R-phase -->\n"
        "<!-- consistency: allow R-phase -->\n"
        "Phase 2 too\n"
        "Phase 1 again, not allowed\n"
    )
    root = make_repo(tmp_path, {"README.md": content}, PHASE_RULE)
    assert [v.line for v in run_forbid(root)] == [4]


def test_inline_allow_must_name_the_rule(tmp_path: Path) -> None:
    content = "Phase 1 <!-- consistency: allow some-other-rule -->\n"
    root = make_repo(tmp_path, {"README.md": content}, PHASE_RULE)
    assert len(run_forbid(root)) == 1


def test_multiline_rule_catches_sentence_split_across_lines(tmp_path: Path) -> None:
    rule = """
[[forbid]]
id = "R-multi"
multiline = true
pattern = '(?is)decisions[^.]{0,70}?documented[^.]{0,40}?architecture\\.md'
why = "đã chuyển"
"""
    content = "Intro.\nKey decisions, documented in full in\n[`docs/architecture.md`].\n"
    root = make_repo(tmp_path, {"README.md": content}, rule)
    [v] = run_forbid(root)
    assert v.line == 2


# --- dead_path ------------------------------------------------------------------------


def run_dead(root: Path) -> list[str]:
    cfg = check.load_config(root)
    tracked = check.tracked_files(root)
    return [v.message for v in check.check_dead_paths(root, tracked, tracked, cfg)]


def test_dead_path_flags_missing_backtick_path(tmp_path: Path) -> None:
    root = make_repo(tmp_path, {"docs/a.md": "see `docs/missing.md`\n", "src/x.py": ""})
    assert run_dead(root) == ["đường dẫn không tồn tại: docs/missing.md"]


def test_dead_path_accepts_existing_planned_untracked_and_module_refs(tmp_path: Path) -> None:
    content = (
        "`src/x.py:12` `src/x.py::fn()` `src/kb/search.py` `data/threads.db`\n"
        "`src/x.helper_fn` `docs/a.md#section`\n"
    )
    root = make_repo(tmp_path, {"docs/a.md": content, "src/x.py": ""})
    assert run_dead(root) == []


def test_dead_path_ignores_globs_placeholders_and_urls(tmp_path: Path) -> None:
    content = "`src/*.py` `docs/rq/RQ-<n>.md` `${DIR}/x.md` [l](https://x.com/a/b)\n"
    root = make_repo(tmp_path, {"docs/a.md": content, "src/x.py": ""})
    assert run_dead(root) == []


def test_markdown_link_resolves_relative_to_file(tmp_path: Path) -> None:
    files = {
        "docs/claude/a.md": "[ok](b.md) [up](../top.md) [bad](nope.md)\n",
        "docs/claude/b.md": "",
        "docs/top.md": "",
    }
    root = make_repo(tmp_path, files)
    assert run_dead(root) == ["đường dẫn không tồn tại: docs/claude/nope.md"]


# --- readme_sync ----------------------------------------------------------------------


def test_readme_shape_mismatch_is_reported(tmp_path: Path) -> None:
    same = "# T\n## A\n| a |\n|---|\n"
    root = make_repo(
        tmp_path,
        {"README.md": same, "README.vi.md": same, "README.fr.md": "# T\n| a |\n|---|\n"},
    )
    [v] = check.check_readme_sync(root, staged=None)
    assert v.path == "README.fr.md" and "headings" in v.message


def test_readme_must_change_together_when_staged(tmp_path: Path) -> None:
    same = "# T\n"
    root = make_repo(tmp_path, {"README.md": same, "README.vi.md": same, "README.fr.md": same})
    rules = [v.rule for v in check.check_readme_sync(root, staged=["README.md"])]
    assert rules == ["readme-together"]
    staged_all = ["README.md", "README.vi.md", "README.fr.md"]
    assert check.check_readme_sync(root, staged=staged_all) == []


def test_commit_mode_scans_whole_repo_but_keeps_readme_together(tmp_path: Path) -> None:
    # Lỗ hổng 2026-10-01: pre-commit chỉ quét file stage → vi phạm ở file KHÁC lọt qua.
    same = "# T\n"
    files = {"README.md": same, "README.vi.md": same, "README.fr.md": same}
    root = make_repo(tmp_path, {**files, "docs/old.md": "ok\n"}, PHASE_RULE)
    (root / "docs/old.md").write_text("Phase 1 plan\n", encoding="utf-8")  # sửa, không stage
    (root / "README.md").write_text("# T\n\nx\n", encoding="utf-8")
    _git(root, "add", "README.md")

    def rules(mode: str) -> list[str]:
        return sorted(v.rule for v in check.run(root, mode, with_pytest=False))

    assert rules("staged") == ["readme-together"]  # bỏ lọt docs/old.md
    assert rules("commit") == ["R-phase", "readme-together"]
    assert rules("all") == ["R-phase"]  # --all không biết file nào đang stage


# --- stale_asset ----------------------------------------------------------------------

ASSET_RULE = """
[[stale_asset]]
id = "R-shot"
adr = "0001"
path = "docs/shot.png"
"""


def test_asset_older_than_adr_is_stale_until_regenerated(tmp_path: Path) -> None:
    root = make_repo(tmp_path, {"docs/shot.png": "old"}, ASSET_RULE)
    adr = root / "docs/decisions/0001-x.md"
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text("# ADR\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "adr", date="2026-02-01T00:00:00")
    cfg = check.load_config(root)
    assert [v.rule for v in check.check_stale_assets(root, cfg)] == ["R-shot"]

    (root / "docs/shot.png").write_text("new", encoding="utf-8")
    assert check.check_stale_assets(root, cfg) == []  # đang làm lại trong working tree
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "regen", date="2026-03-01T00:00:00")
    assert check.check_stale_assets(root, cfg) == []


def test_asset_regenerated_with_same_timestamp_or_same_commit_is_fresh(tmp_path: Path) -> None:
    # Squash/rebase merge trên GitHub: cùng committer date, hoặc ADR + ảnh trong 1 commit.
    # So theo timestamp (`<=`) từng báo sai vĩnh viễn; so theo tổ tiên commit thì đúng.
    root = make_repo(tmp_path, {"docs/shot.png": "old"}, ASSET_RULE)
    cfg = check.load_config(root)
    adr = root / "docs/decisions/0001-x.md"
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text("# ADR\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "adr", date="2026-02-01T00:00:00")
    (root / "docs/shot.png").write_text("new", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "regen", date="2026-02-01T00:00:00")  # cùng giây
    assert check.check_stale_assets(root, cfg) == []

    (tmp_path / "sq").mkdir()
    squashed = make_repo(tmp_path / "sq", {"docs/shot.png": "x"}, ASSET_RULE)
    sq_adr = squashed / "docs/decisions/0001-x.md"
    sq_adr.parent.mkdir(parents=True, exist_ok=True)
    sq_adr.write_text("# ADR\n", encoding="utf-8")
    (squashed / "docs/shot.png").write_text("new", encoding="utf-8")
    _git(squashed, "add", "-A")
    _git(squashed, "commit", "-q", "-m", "adr + regen", date="2026-02-01T00:00:00")
    assert check.check_stale_assets(squashed, check.load_config(squashed)) == []


def test_commit_mode_accepts_tracked_dirs_and_module_refs(tmp_path: Path) -> None:
    files = {
        "docs/a.md": "See `src/pkg/mod.func` and `src/pkg` and `src/pkg/`\n",
        "src/pkg/mod.py": "def func() -> None: ...\n",
    }
    root = make_repo(tmp_path, files)
    assert check.run(root, "commit", with_pytest=False) == []


def test_commit_mode_dead_path_requires_tracked_file(tmp_path: Path) -> None:
    # Doc đã track nhắc file chưa `git add`: trên đĩa có, ở clone sạch / CI thì không
    root = make_repo(tmp_path, {"docs/a.md": "See `src/new_mod.py`\n"})
    (root / "src").mkdir()
    (root / "src/new_mod.py").write_text("x = 1\n", encoding="utf-8")  # chưa track
    assert [v.rule for v in check.run(root, "all", with_pytest=False)] == []
    assert [v.rule for v in check.run(root, "commit", with_pytest=False)] == ["dead-path"]
    _git(root, "add", "src/new_mod.py")
    assert check.run(root, "commit", with_pytest=False) == []


# --- doc_limits + chỉ mục ADR ---------------------------------------------------------


def test_doc_limits_and_adr_index(tmp_path: Path) -> None:
    rules = '\n[[max_lines]]\npath = "CLAUDE.md"\nmax = 2\n'
    files = {
        "CLAUDE.md": "a\nb\nc\n",
        "docs/decisions/README.md": "| [0001](0001-a.md) |\n",
        "docs/decisions/0000-template.md": "",
        "docs/decisions/0001-a.md": "- **Trạng thái**: Accepted\n- **Ngày**: 2026-09-30\n",
        "docs/decisions/0002-b.md": "- **Trạng thái**: Accepted\n",
    }
    root = make_repo(tmp_path, files, rules)
    got = sorted(
        (v.rule, v.path)
        for v in check.check_doc_limits(root, check.load_config(root), check.tracked_files(root))
    )
    assert got == [
        ("adr-fields", "docs/decisions/0002-b.md"),
        ("adr-index", "docs/decisions/0002-b.md"),
        ("max-lines:CLAUDE.md", "CLAUDE.md"),
    ]


# --- count_fact -----------------------------------------------------------------------


def test_count_fact_flags_stale_numbers_only(tmp_path: Path) -> None:
    rules = """
[[count_fact]]
id = "R-count"
pattern = '(?P<n>\\d+)(%20|\\s)+tests?'
paths = ["README*.md"]
"""
    content = "![b](tests-183%20passing)\nWe have 183 tests.\nOld: 99 tests.\n"
    root = make_repo(tmp_path, {"README.md": content}, rules)
    cfg = check.load_config(root)
    got = check.check_count_facts(root, ["README.md"], cfg, actual=183)
    assert [v.line for v in got] == [3]


def test_commit_mode_does_not_count_untracked_test_files(tmp_path: Path) -> None:
    # File test dở dang chưa `git add` không thuộc commit → không được làm sai số đếm
    rules = """
[[count_fact]]
id = "R-count"
pattern = '(?P<n>\\d+) tests?'
paths = ["README*.md"]
"""
    test_src = "def test_x() -> None:\n    assert True\n"
    root = make_repo(tmp_path, {"README.md": "1 test\n", "tests/test_a.py": test_src}, rules)
    (root / "tests/test_wip.py").write_text(test_src, encoding="utf-8")  # chưa track
    assert check.collected_test_count(root) == 2
    assert [v.rule for v in check.run(root, "all")] == ["R-count"]  # --all: báo để cập nhật
    assert check.run(root, "commit") == []


# --- sổ luật thật ---------------------------------------------------------------------


def test_real_invariants_catch_known_lapses(tmp_path: Path) -> None:
    """7 kiểu lỗi thời tìm thấy ngày 2026-09-30 phải luôn bị luật thật bắt."""
    lapses = {
        "ADR0001-phase12": "![Status](https://img.shields.io/badge/status-Phase%201-orange)",
        "KB-no-separate-vectorstore": "cần vector store riêng (Chroma/FAISS)",
        "ADR0003-sprint-steps": "việc của RAG — Bước 10, hoãn",
        "ADR0003-old-docs": "xem decisions log trong architecture.md",
        "FACT-design-sync-direction": "Chạy `/design-sync` để pull component",
        "DATA-replies-are-author": "the 1,285 audience/self-replies",
        "ADR0001-coming-soon": "phân loại live/coming soon",
    }
    root = tmp_path / "repo"
    (root / "docs/decisions").mkdir(parents=True)
    real_toml = (REPO_ROOT / check.INVARIANTS_PATH).read_text(encoding="utf-8")
    (root / check.INVARIANTS_PATH).write_text(real_toml, encoding="utf-8")
    notes = root / "docs/claude/notes.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("\n".join(lapses.values()) + "\n", encoding="utf-8")
    multi = "Decisions, documented in full in\n[`docs/claude/architecture.md`].\n"
    (root / "readme_like.md").write_text(multi, encoding="utf-8")

    cfg = check.load_config(root)
    found = {
        v.rule for v in check.check_forbid(root, ["docs/claude/notes.md", "readme_like.md"], cfg)
    }
    assert set(lapses) | {"ADR0003-decisions-location"} <= found


def test_real_invariants_do_not_flag_threads_api_enum(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs/decisions").mkdir(parents=True)
    real_toml = (REPO_ROOT / check.INVARIANTS_PATH).read_text(encoding="utf-8")
    (root / check.INVARIANTS_PATH).write_text(real_toml, encoding="utf-8")
    (root / "m.py").write_text('CAROUSEL_ALBUM = "CAROUSEL_ALBUM"\n', encoding="utf-8")
    assert check.check_forbid(root, ["m.py"], check.load_config(root)) == []


@pytest.mark.parametrize(
    ("rule", "text", "flagged"),
    [
        # ADR-0016: model cũ, kể cả cuối câu; không bắt đời mới hơn
        ("ADR0016-opus-labeling", "Clusters are labeled by claude-opus-5.", True),
        ("ADR0016-opus-labeling", "`claude-opus-5`", True),
        ("ADR0016-opus-labeling", "fallback: claude-opus-5-5", False),
        ("ADR0016-opus-labeling", "claude-opus-5.5 or claude-opus-50", False),
        ("ADR0016-prompt-caching", "Claude API (cluster labeling + prompt caching)", True),
        ("ADR0016-prompt-caching", "uses Prompt-Caching", True),
        ("ADR0016-prompt-caching", "mise en cache du prompt", True),
        ("ADR0016-prompt-caching", "Threads API client with response caching", False),
        # ADR-0017: job NLP không còn chạy đêm
        ("ADR0017-nlp-3am", "`ThreadsAI_NLPClusterJob_Daily` (3h sáng)", True),
        ("ADR0017-nlp-3am", "(hằng ngày 3h: src/pipeline/nlp_cluster_job)", True),
        ("ADR0017-nlp-3am", "the NLP job runs at 3:00 AM", True),
        ("ADR0017-nlp-3am", "recluster lúc 03h00", True),
        ("ADR0017-nlp-3am", "nightly cluster refresh", True),
        ("ADR0017-nlp-3am", "chi phí gom cụm hằng đêm", True),
        ("ADR0017-nlp-3am", "chi phí đặt tên hằng đêm thấp hơn", True),
        ("ADR0017-nlp-3am", "NLP job at 3h30", True),
        ("ADR0017-nlp-3am", "NLP job daily at 12:30", False),
        ("ADR0017-nlp-3am", "3 amplification metrics per cluster", False),
        ("ADR0017-nlp-3am", "cluster 3 among 9", False),
        ("ADR0017-nlp-3am", "delta amplification over 3h -> 2.0/h", False),
        ("ADR0017-nlp-3am", "snapshot every 4h", False),
        ("ADR0017-old-script", "run scripts/set_job_actions.ps1", True),
        ("ADR0017-old-script", "run scripts/configure_jobs.ps1", False),
    ],
)
def test_real_rules_for_model_and_schedule_decisions(
    tmp_path: Path, rule: str, text: str, flagged: bool
) -> None:
    root = tmp_path / "repo"
    (root / "docs/decisions").mkdir(parents=True)
    real_toml = (REPO_ROOT / check.INVARIANTS_PATH).read_text(encoding="utf-8")
    (root / check.INVARIANTS_PATH).write_text(real_toml, encoding="utf-8")
    notes = root / "docs/claude/notes.md"  # nằm trong `paths` của luật prompt-caching
    notes.parent.mkdir(parents=True)
    notes.write_text(text + "\n", encoding="utf-8")
    found = {
        v.rule for v in check.check_forbid(root, ["docs/claude/notes.md"], check.load_config(root))
    }
    assert (rule in found) is flagged


def test_real_sprint_step_rule_ignores_procedure_numbering_in_skills(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs/decisions").mkdir(parents=True)
    real_toml = (REPO_ROOT / check.INVARIANTS_PATH).read_text(encoding="utf-8")
    (root / check.INVARIANTS_PATH).write_text(real_toml, encoding="utf-8")
    skill = root / ".claude/skills/x/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("## Bước 1 — Quyết định\n", encoding="utf-8")
    code = root / "src/m.py"
    code.parent.mkdir(parents=True)
    code.write_text("# việc của RAG — Bước 10, hoãn\n", encoding="utf-8")
    cfg = check.load_config(root)
    files = [".claude/skills/x/SKILL.md", "src/m.py"]
    got = [(v.path, v.rule) for v in check.check_forbid(root, files, cfg)]
    assert ("src/m.py", "ADR0003-sprint-steps") in got
    assert all(path != ".claude/skills/x/SKILL.md" for path, _ in got)


# Luật học được từ lượt /decision-sweep đầu tiên (consistency-auditor): mỗi luật 1 ví dụ
# PHẢI khớp và 1 ví dụ KHÔNG được khớp, lấy từ chính phát hiện thật trong repo.
LEARNED_RULES = [
    (
        "ADR0003-arch-md-see",
        "tests/x.py",
        'reason="blocked by Application Control Policy — see architecture.md",',
        "# Xem docs/claude/architecture.md mục Tech stack",
    ),
    (
        "ADR0001-autopost",
        "docs/claude/x.md",
        "POST /me/threads  # Publish post mới (nếu tích hợp auto-post)",
        "Không đăng gì lên Threads.",
    ),
    (
        "ADR0001-publish-scope",
        "docs/claude/x.md",
        "- Scope đang dùng: `threads_basic`, `threads_content_publish`",
        "- Scope đang dùng: `threads_basic`. Đã cấp nhưng không dùng: `threads_content_publish`",
    ),
    (
        "ADR0001-rag-gen-scope",
        "docs/claude/x.md",
        "- RAG: bản nhẹ (retrieval + generation cơ bản)",
        "- Knowledge base: chỉ truy xuất + đánh giá",
    ),
    (
        "ADR0001-svm-in-pipeline",
        "docs/claude/x.md",
        "(việc đó là HDBSCAN + SVM-RBF/LogReg)",
        "bậc thang baseline → SVM-RBF",
    ),
    ("ADR0001-content-idea", "docs/claude/x.md", "cấu trúc Content Idea Card", "Content unit row"),
    (
        "DATA-stale-reply-count",
        "src/x.py",
        "phục vụ 1.285 replies đã ingest",
        "# Verify live 2026-08-31 (140 posts + 1,285 replies)",
    ),
    (
        "DATA-audience-reply-field",
        "docs/claude/x.md",
        "Phân biệt self-continuation vs audience reply",
        "phân vai reply ở Phase D0",
    ),
    (
        "ADR0003-arch-decision-pointer",
        "src/x.py",
        "xem docs/claude/architecture.md decision log 2026-09-02",
        "## 13. Decision log",
    ),
    (
        "ADR0003-status-in-claude",
        "docs/claude/x.md",
        "[`CLAUDE.md`](../../CLAUDE.md) cho mission/status.",
        "Tài liệu gọn (CLAUDE.md, status, roadmap, ADR)",
    ),
    (
        "ADR0003-sprint-word",
        "docs/claude/x.md",
        "### V2 (không scope vào sprint hiện tại)",
        "plan/sprint cũ, giữ nguyên văn",
    ),
    (
        "ADR0003-harness-counts",
        "docs/status.md",
        "hooks, 3 subagent, 7 skill",
        "subagents code-reviewer, qa-tester",
    ),
    (
        "DS-landing-built",
        "docs/claude/x.md",
        "Tầng B landing page chưa dựng.",
        "(Tầng B, scoped — xem design-system)",
    ),
    (
        "FACT-design-sync-wording",
        "docs/claude/dev-rules.md",
        "4. Claude Code verify: code sync có khớp token",
        "4. Claude Code verify: code đã port có khớp token",
    ),
    (
        "ADR0008-pytest-slow",
        "CLAUDE.md",
        "uv run pytest -q   # test (hiện chậm ~5 phút trên Windows)",
        "- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy)",
    ),
    (
        "ADR0008-mypy-scope",
        ".claude/rules/python.md",
        "mypy **strict** trên `src/` + `tests/` —",
        "mypy **strict** trên `src/` + `tests/` + `scripts/` —",
    ),
    (
        "ADR0008-precommit-scope",
        ".claude/hooks/x.py",
        "--no-verify skips ruff/mypy/commit-msg hooks",
        "skips the ruff, mypy, consistency hooks",
    ),
    (
        "ADR0009-old-name",
        "src/dashboard/src/app/layout.tsx",
        '  title: "Threads AI Content",',
        "cd threads-ai-content && uv sync",
    ),
    (
        "ADR0009-slug-as-title",
        "CLAUDE.md",
        "# threads-ai-content",
        "# Unthreaded (repo `threads-ai-content`)",
    ),
    (
        "ADR0009-slug-as-title",
        "docs/roadmap.md",
        "# Roadmap — threads-ai-content",
        "cd threads-ai-content",
    ),
    (
        "ADR0009-old-name-variants",
        "README.md",
        "The Threads AI dashboard, see Threads-AI-content.",
        "Task Scheduler `ThreadsAI_SnapshotJob_4h` in threads-ai-content/",
    ),
    (
        "ADR0010-postgres",
        "README.md",
        "| Database | SQLite (dev) → PostgreSQL (planned before any multi-user use) | Live (dev) |",
        "| Database | SQLite — one file, one writer, knowledge base included | Live |",
    ),
    (
        "ADR0004-inflated-continuations",
        "docs/status.md",
        "trung bình 6.84 continuation mỗi bài",
        "trung bình 1.91 continuation mỗi bài (đo 2026-10-01)",
    ),
    (
        "ADR0004-loose-role-counts",
        "docs/claude/x.md",
        "1.368 reply (362 self-continuation, 664 trả lời follower)",
        "353 self_continuation / 674 author_answer / 342 outbound",
    ),
    (
        "ADR0004-comment-replies",
        "src/x.py",
        "# Posts and comment replies recommending groceries",
        "# Posts recommending groceries",
    ),
    (
        "ADR0004-fixed-method",
        ".claude/rules/x.md",
        "không đụng `method='fixed'`",
        "chỉ còn method cluster",
    ),
    (
        "ADR0004-fixed-schema-option",
        "docs/claude/x.md",
        '`topics` (id, method: "fixed"|"cluster")',
        "## 6 fixed category (câu hỏi nghiên cứu RQ-08)",
    ),
    (
        "ADR0004-conversation-unverified",
        ".claude/rules/x.md",
        "bình luận follower chưa ingest (Phase D0 sẽ verify `/{id}/conversation`)",
        "`/{id}/conversation` đã verify live 2026-10-01; chưa lưu — cần ADR-0007",
    ),
    (
        "ADR0004-ari-not-measurable",
        ".claude/skills/x/SKILL.md",
        "- ARI giữa lần trước và lần này: **chưa có** cho tới khi embeddings được persist",
        "- ARI so với lần trước: cột `ari_vs_previous` của `cluster_runs`",
    ),
    (
        "ADR0004-role-count-english",
        "src/x.py",
        "# 286 self_continuation / 741 author_answer / 342 outbound",
        "# 353 self_continuation / 674 author_answer / 342 outbound",
    ),
    (
        "ADR0004-dbcv-unnamed",
        "docs/status.md",
        "- 9 cluster (DBCV 0,317, nhiễu 36%)",
        "- 9 cluster (`validity_index` 0,317, nhiễu 36%)",
    ),
    (
        "ADR0004-dbcv-unnamed",
        "docs/claude/x.md",
        "validity_index 0,317 và DBCV 0,205",
        "| B | DBCV (`relative_validity_`) | 0.205 |",
    ),
    (
        "ADR0004-dbcv-unnamed",
        "src/x.py",
        "# | B | DBCV | 0.205 |",
        "    dbcv=0.3,  # validity_index",
    ),
    (
        "ADR0004-nn10-current",
        "docs/claude/architecture.md",
        "| Topic discovery | HDBSCAN (`leaf`, `min_cluster_size=4`, `n_neighbors=10`) | Live |",
        "| Topic discovery | HDBSCAN (`leaf`, `min_cluster_size=4`, `n_neighbors=8`) | Live |",
    ),
    (
        "ADR0013-bat-launcher",
        ".claude/skills/recluster/SKILL.md",
        "- Chạy: `cmd //c run_nlp_cluster_job.bat` — export → cluster → import",
        "- Chạy: `uv run python -m src.pipeline.nlp_cluster_job`",
    ),
    (
        "ADR0013-lastline-health",
        ".claude/skills/recluster/SKILL.md",
        "2. Xem dòng cuối `data/logs/scheduled_job.log`; nếu job vừa bắt đầu thì chờ.",
        '2. `uv run python -m scripts.job_health` — ghi "task running now" thì chờ.',
    ),
    (
        "ADR0015-optional-review",
        ".claude/skills/checkpoint/SKILL.md",
        "Thay đổi có logic → đề xuất gọi `@agent-code-reviewer` trước.",
        "Diff có file logic → `@agent-code-reviewer` bắt buộc (ADR-0015).",
    ),
]


@pytest.mark.parametrize(("rule_id", "path", "hit", "miss"), LEARNED_RULES)
def test_learned_rules_hit_and_miss(
    tmp_path: Path, rule_id: str, path: str, hit: str, miss: str
) -> None:
    root = tmp_path / "repo"
    (root / "docs/decisions").mkdir(parents=True)
    real_toml = (REPO_ROOT / check.INVARIANTS_PATH).read_text(encoding="utf-8")
    (root / check.INVARIANTS_PATH).write_text(real_toml, encoding="utf-8")
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    cfg = check.load_config(root)

    target.write_text(hit + "\n", encoding="utf-8")
    assert rule_id in {v.rule for v in check.check_forbid(root, [path], cfg)}

    target.write_text(miss + "\n", encoding="utf-8")
    assert rule_id not in {v.rule for v in check.check_forbid(root, [path], cfg)}
