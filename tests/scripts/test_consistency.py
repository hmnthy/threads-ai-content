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
