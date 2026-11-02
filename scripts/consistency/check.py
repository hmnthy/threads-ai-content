"""Cảnh sát nhất quán (tầng 1): kiểm repo có khớp các quyết định đã chốt không.

Luật nằm ở `docs/decisions/invariants.toml` — mỗi luật gắn với 1 ADR (hoặc 1 phát hiện
có ngày). Script chỉ dùng thư viện chuẩn để chạy được ở pre-commit, hook và CI.

Các kiểm tra:
1. forbid       — mẫu (regex) lỗi thời bị cấm, trừ vùng `allow` và ngoại lệ có chú thích
2. dead_path    — đường dẫn trong backtick / link markdown phải tồn tại (trừ planned/untracked)
3. readme_sync  — 3 README (EN/VI/FR) cùng cấu trúc; sửa 1 bản phải sửa cả 3 (--staged/--commit)
4. stale_asset  — file nhị phân phải được làm lại trong/sau commit tạo ADR làm nó lỗi thời
5. doc_limits   — giới hạn số dòng (CLAUDE.md, status.md) + chỉ mục ADR đầy đủ
6. count_fact   — số test ghi trong docs khớp số test thật (--all/--commit)
7. ui_contract  — hợp đồng UI (ADR-0020): `ui-contract.md` xét đủ mọi ADR, mốc "Cập nhật tới"
                  không tụt sau ADR mới nhất, id không trùng, luật/test ở cột "Kiểm bằng" có thật;
                  ADR từ `ui_impact_from` có mục "### Hệ quả UI"
8. ref_anchor   — tham chiếu code trong docs ghi `path:N#Tên`, dòng N (…M) còn chứa Tên (ADR-0033);
                  thứ trông như tham chiếu mà không đọc được / tên file trùng → vi phạm;
                  `--fix-refs` dời số theo diff code so với HEAD, không thì về chỗ duy nhất

Mockup (`mockup_paths`, của Claude Design) chỉ bị quét bởi luật forbid có `mockups = true`, và
vi phạm ở đó là CẢNH BÁO (severity "warn"): in ra, ghi audit, nhưng không chặn commit (ADR-0020).

Ngoại lệ có dấu vết: chú thích `consistency: allow <rule-id>` trên cùng dòng hoặc dòng
ngay trước. Dùng:  uv run python -m scripts.consistency.check --all [--json] [--fix-refs]

Harness Claude Code (`.claude/`) gitignored, có kho git riêng (ADR-0027): --all quét thêm bản
trên đĩa (nếu có) để /decision-sweep vẫn phủ skill/agent/rule; --commit, --staged và CI không quét
nội dung harness — chỉ kiểm đường dẫn `.claude/...` có thật trên đĩa khi máy có harness.

Chế độ: --all (toàn repo; hook đầu phiên, sweep, CI) · --commit (pre-commit: toàn repo +
luật "3 README sửa cùng nhau" theo file đang stage — ~6 giây) · --staged (chỉ file stage).
Pre-commit quét toàn repo vì luật đếm số / ảnh lỗi thời / đường dẫn chết hỏng do file KHÁC
file đang sửa (VD thêm test làm README ghi sai số test) — chỉ quét file stage thì lọt.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys
import tomllib
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

INVARIANTS_PATH = "docs/decisions/invariants.toml"
README_FILES = ("README.md", "README.vi.md", "README.fr.md")
ALLOW_MARK = "consistency: allow"
# Harness riêng tư (ADR-0027): thư mục con không phải harness — worktree (cả repo lồng
# trong đó), `.git` lạc (kho riêng đúng chuẩn là bare NGOÀI `.claude/`), bộ nhớ agent cục bộ
HARNESS_DIR = ".claude"
# "Máy có harness" = có file này; thư mục `.claude/` trần có thể chỉ chứa phần cục bộ
# (settings.local.json, agent-memory/) ở worktree chưa copy harness
HARNESS_SENTINEL = ".claude/settings.json"
# agent-memory/: ghi chú subagent (`memory: project`) — dữ liệu của máy, không phải harness
HARNESS_SKIP_DIRS = frozenset({"worktrees", ".git", "agent-memory", "agent-memory-local"})
HARNESS_SKIP_FILES = frozenset({"settings.local.json"})

# Backtick span hoặc đích link markdown `](...)`
_BACKTICK = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
_ADR_FILE = re.compile(r"^(\d{4})-.+\.md$")


@dataclass(frozen=True)
class Violation:
    check: str
    rule: str
    path: str
    line: int
    message: str
    fix: str = ""
    adr: str = ""
    # "error" chặn commit; "warn" chỉ báo (vi phạm trong mockup của Claude Design, ADR-0020)
    severity: Literal["error", "warn"] = "error"


@dataclass
class Config:
    exclude: list[str] = field(default_factory=list)
    dead_path_exclude: list[str] = field(default_factory=list)
    planned_paths: list[str] = field(default_factory=list)
    known_untracked: list[str] = field(default_factory=list)
    mockup_paths: list[str] = field(default_factory=list)
    ui_contract: str = ""
    ui_impact_from: int = 0
    forbid: list[dict[str, Any]] = field(default_factory=list)
    stale_assets: list[dict[str, Any]] = field(default_factory=list)
    max_lines: list[dict[str, Any]] = field(default_factory=list)
    count_facts: list[dict[str, Any]] = field(default_factory=list)


def load_config(root: Path) -> Config:
    data = tomllib.loads((root / INVARIANTS_PATH).read_text(encoding="utf-8"))
    settings = data.get("settings", {})
    return Config(
        exclude=settings.get("exclude", []),
        dead_path_exclude=settings.get("dead_path_exclude", []),
        planned_paths=settings.get("planned_paths", []),
        known_untracked=settings.get("known_untracked", []),
        mockup_paths=settings.get("mockup_paths", []),
        ui_contract=settings.get("ui_contract", ""),
        ui_impact_from=int(settings.get("ui_impact_from", 0)),
        forbid=data.get("forbid", []),
        stale_assets=data.get("stale_asset", []),
        max_lines=data.get("max_lines", []),
        count_facts=data.get("count_fact", []),
    )


def errors_only(violations: list[Violation]) -> list[Violation]:
    return [v for v in violations if v.severity == "error"]


def _matches(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        # quotepath=off: tên file có dấu (tiếng Việt) không bị git trả về dạng "r\303\251…"
        ["git", "-C", str(root), "-c", "core.quotepath=off", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.stdout


def tracked_files(root: Path) -> list[str]:
    return [p for p in _git(root, "ls-files").splitlines() if p]


def untracked_files(root: Path) -> list[str]:
    """File mới chưa `git add` (bỏ file gitignored) — --all quét cả chúng: file mới viết
    xong chưa stage vẫn phải được kiểm trước khi tới pre-commit (lỗ hổng 2026-10-01)."""
    out = _git(root, "ls-files", "--others", "--exclude-standard")
    return [p for p in out.splitlines() if p]


def harness_files(root: Path) -> list[str]:
    """File harness `.claude/` trên đĩa — gitignored nên `ls-files` không thấy (ADR-0027).
    Cắt nhánh `os.walk` ở thư mục bỏ qua: `worktrees/` chứa nguyên repo + node_modules."""
    base = root / HARNESS_DIR
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        skip = HARNESS_SKIP_DIRS if Path(dirpath) == base else {".git"}
        # os.walk không theo symlink nhưng VẪN theo junction Windows (islink = False)
        dirnames[:] = [
            d
            for d in dirnames
            if d not in skip and not os.path.isjunction(os.path.join(dirpath, d))
        ]
        for name in filenames:
            if name not in HARNESS_SKIP_FILES:
                out.append((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(out)


def staged_files(root: Path) -> list[str]:
    out = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [p for p in out.splitlines() if p]


def read_text(path: Path) -> str | None:
    """Trả nội dung nếu là file text UTF-8 nhỏ; None với file nhị phân/lớn/không đọc được."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > 1_000_000 or b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _allowed_inline(lines: list[str], idx: int, rule_id: str) -> bool:
    for j in (idx, idx - 1):
        if 0 <= j < len(lines) and ALLOW_MARK in lines[j]:
            tail = lines[j].split(ALLOW_MARK, 1)[1]
            ids = re.findall(r"[\w.-]+", tail)
            if rule_id in ids:
                return True
    return False


# --- 1. forbid ------------------------------------------------------------------------


def _forbid_hits(
    rule: dict[str, Any], pattern: re.Pattern[str], text: str
) -> list[tuple[int, str]]:
    """(chỉ số dòng 0-based, đoạn khớp). `multiline = true` → khớp trên cả file (câu vắt dòng)."""
    if rule.get("multiline"):
        return [
            (text.count("\n", 0, m.start()), " ".join(m.group(0).split()))
            for m in pattern.finditer(text)
        ]
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines()):
        m = pattern.search(line)
        if m:
            hits.append((i, m.group(0)))
    return hits


def check_forbid(root: Path, files: list[str], cfg: Config) -> list[Violation]:
    compiled = [(rule, re.compile(rule["pattern"])) for rule in cfg.forbid]
    out: list[Violation] = []
    for rel in files:
        # Mockup: được quét dù nằm trong `exclude`, nhưng chỉ bởi luật `mockups = true`
        mockup = _matches(rel, cfg.mockup_paths)
        if not mockup and _matches(rel, cfg.exclude):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        for rule, pattern in compiled:
            if _matches(rel, rule.get("allow", [])):
                continue
            if mockup:
                if not rule.get("mockups"):
                    continue
            else:
                only = rule.get("paths")
                if only and not _matches(rel, only):
                    continue
            for i, snippet in _forbid_hits(rule, pattern, text):
                if _allowed_inline(lines, i, rule["id"]):
                    continue
                out.append(
                    Violation(
                        check="forbid",
                        rule=rule["id"],
                        path=rel,
                        line=i + 1,
                        message=f"'{snippet}' — {rule['why']}",
                        fix=rule.get("fix", ""),
                        adr=str(rule.get("adr", "")),
                        severity="warn" if mockup else "error",
                    )
                )
    return out


# --- 2. dead_path ---------------------------------------------------------------------


def _top_level_names(root: Path, tracked: list[str], cfg: Config) -> set[str]:
    names = {p.split("/", 1)[0] for p in tracked}
    names |= {p.name for p in root.iterdir()}
    for g in cfg.planned_paths + cfg.known_untracked:
        names.add(g.split("/", 1)[0])
    return names


def _clean_candidate(raw: str) -> str | None:
    cand = raw.strip().strip("'\"")
    if not cand or " " in cand or any(ch in cand for ch in "*<>{}$|?"):
        return None
    if cand.startswith(("http://", "https://", "#", "~", "mailto:", "@")):
        return None
    cand = cand.split("#", 1)[0]
    cand = cand.split("::", 1)[0].split("(", 1)[0]  # src/config.py::db_path() → file
    cand = re.sub(r":\d+(-\d+)?$", "", cand)  # file.py:42 hoặc :42-51
    cand = cand.rstrip(".,;:)")
    if cand.startswith("./"):
        cand = cand[2:]
    return cand or None


def _tracked_index(tracked: list[str]) -> frozenset[str]:
    """File đã track + mọi thư mục cha của chúng (để kiểm cả đường dẫn thư mục)."""
    out: set[str] = set(tracked)
    for f in tracked:
        parts = f.split("/")
        out.update("/".join(parts[:i]) for i in range(1, len(parts)))
    return frozenset(out)


def _path_ok(root: Path, rel_path: str, cfg: Config, tracked: frozenset[str] | None = None) -> bool:
    """`tracked` (chế độ commit): đường dẫn phải có trong git, không chỉ trên đĩa — doc nhắc
    file chưa `git add` qua được pre-commit rồi hỏng ở clone sạch / CI."""
    norm = rel_path.rstrip("/")

    def present(rel: str) -> bool:
        return rel in tracked if tracked is not None else (root / rel).exists()

    if present(norm):
        return True
    # Tham chiếu kiểu module Python: src/api/endpoints.get_x → src/api/endpoints.py
    head, _, last = norm.rpartition("/")
    module = f"{head}/{last.split('.', 1)[0]}.py" if "." in last else None
    if module and present(module):
        return True
    if _matches(norm, cfg.planned_paths):
        return True
    # Harness có trên máy → kiểm thật trên đĩa, kể cả chế độ commit (không có trong git);
    # `known_untracked` chỉ cho qua khi máy không có harness (CI, clone, worktree) — ADR-0027
    if _is_harness_path(norm) and (root / HARNESS_SENTINEL).is_file():
        return (root / norm).exists() or bool(module and (root / module).exists())
    return _matches(norm, cfg.known_untracked)


def _is_harness_path(norm: str) -> bool:
    """File/thư mục của harness — trừ phần cục bộ của máy (worktree, kho git riêng, …)."""
    parts = norm.split("/")
    return (
        len(parts) > 1
        and parts[0] == HARNESS_DIR
        and parts[1] not in HARNESS_SKIP_DIRS | HARNESS_SKIP_FILES
    )


def check_dead_paths(
    root: Path, files: list[str], tracked: list[str], cfg: Config, strict: bool = False
) -> list[Violation]:
    tops = _top_level_names(root, tracked, cfg)
    index = _tracked_index(tracked) if strict else None
    out: list[Violation] = []
    for rel in files:
        if _matches(rel, cfg.exclude) or _matches(rel, cfg.dead_path_exclude):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        base = posixpath.dirname(rel)
        is_md = rel.endswith(".md")
        for i, line in enumerate(lines):
            candidates: list[tuple[str, bool]] = [(c, False) for c in _BACKTICK.findall(line)]
            if is_md:
                candidates += [(c, True) for c in _MD_LINK.findall(line)]
            for raw, is_link in candidates:
                cand = _clean_candidate(raw)
                if cand is None:
                    continue
                if is_link:
                    # Link markdown: tương đối so với thư mục của file chứa nó
                    rel_target = posixpath.normpath(posixpath.join(base, cand))
                    if rel_target.startswith("..") or rel_target.split("/", 1)[0] not in tops:
                        continue
                else:
                    # Backtick: quy ước đường dẫn tính từ root repo
                    if "/" not in cand and not cand.endswith(".md"):
                        continue
                    if cand.split("/", 1)[0] not in tops:
                        continue
                    rel_target = cand
                if _path_ok(root, rel_target, cfg, index):
                    continue
                if _allowed_inline(lines, i, "dead-path"):
                    continue
                out.append(
                    Violation(
                        check="dead_path",
                        rule="dead-path",
                        path=rel,
                        line=i + 1,
                        message=f"đường dẫn không tồn tại: {rel_target}",
                        fix="Sửa đường dẫn, hoặc thêm vào planned_paths nếu là file sắp tạo",
                    )
                )
    return out


# --- 3. readme_sync -------------------------------------------------------------------


def _readme_shape(text: str) -> dict[str, int]:
    lines = text.splitlines()
    return {
        "headings": sum(1 for ln in lines if re.match(r"^#{1,6} ", ln)),
        "tables": sum(1 for ln in lines if re.match(r"^\|\s*:?-{3,}", ln)),
        "images": sum(ln.count("<img") + ln.count("![") for ln in lines),
        "code_blocks": sum(1 for ln in lines if ln.startswith("```")),
    }


def check_readme_sync(root: Path, staged: list[str] | None) -> list[Violation]:
    out: list[Violation] = []
    present = [f for f in README_FILES if (root / f).exists()]
    if len(present) < 2:
        return out
    shapes = {f: _readme_shape((root / f).read_text(encoding="utf-8")) for f in present}
    ref = shapes[present[0]]
    for f in present[1:]:
        for key, value in shapes[f].items():
            if value != ref[key]:
                out.append(
                    Violation(
                        check="readme_sync",
                        rule="readme-shape",
                        path=f,
                        line=0,
                        message=f"{key}: {value} ≠ {ref[key]} trong {present[0]}",
                        fix="3 README phải cùng cấu trúc — sửa bản lệch cho khớp",
                    )
                )
    if staged is not None:
        touched = [f for f in present if f in staged]
        if touched and len(touched) != len(present):
            missing = [f for f in present if f not in touched]
            out.append(
                Violation(
                    check="readme_sync",
                    rule="readme-together",
                    path=", ".join(touched),
                    line=0,
                    message=f"sửa {', '.join(touched)} nhưng không sửa {', '.join(missing)}",
                    fix="Sửa cả 3 README trong cùng commit",
                )
            )
    return out


# --- 4. stale_asset -------------------------------------------------------------------


# So theo TỔ TIÊN commit, không theo timestamp: squash/rebase merge trên GitHub đặt cùng
# 1 committer date cho cả chuỗi → so `<=` thời gian báo sai vĩnh viễn (code-reviewer
# 2026-10-01). ADR và asset trong CÙNG commit = asset đã được làm lại cùng ADR → hợp lệ.
def _first_commit(root: Path, pattern: str) -> str | None:
    out = _git(root, "log", "--diff-filter=A", "--format=%H", "--", pattern).split()
    return out[-1] if out else None


def _last_commit(root: Path, path: str) -> str | None:
    out = _git(root, "log", "-1", "--format=%H", "--", path).strip()
    return out or None


def _is_ancestor(root: Path, ancestor: str, commit: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, commit],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def check_stale_assets(root: Path, cfg: Config) -> list[Violation]:
    out: list[Violation] = []
    for rule in cfg.stale_assets:
        path = rule["path"]
        adr = str(rule["adr"])
        adr_commit = _first_commit(root, f"docs/decisions/{adr}-*.md")
        if adr_commit is None:
            continue  # ADR chưa commit — chưa có mốc để so
        if _git(root, "status", "--porcelain", "--", path).strip():
            continue  # đang được làm lại trong working tree / staged
        asset_commit = _last_commit(root, path)
        if asset_commit is None or not _is_ancestor(root, adr_commit, asset_commit):
            out.append(
                Violation(
                    check="stale_asset",
                    rule=rule["id"],
                    path=path,
                    line=0,
                    message=f"cũ hơn ADR-{adr} — nội dung có thể không còn đúng",
                    fix=rule.get("regenerate", "Làm lại file này"),
                    adr=adr,
                )
            )
    return out


# --- 5. doc_limits + chỉ mục ADR ------------------------------------------------------


def check_doc_limits(root: Path, cfg: Config, tracked: list[str]) -> list[Violation]:
    """`tracked` = file git theo dõi (gồm file đã stage) — ADR chưa `git add` không chặn commit."""
    out: list[Violation] = []
    for rule in cfg.max_lines:
        p = root / rule["path"]
        if p.exists():
            n = len(p.read_text(encoding="utf-8").splitlines())
            if n > rule["max"]:
                out.append(
                    Violation(
                        check="doc_limits",
                        rule=f"max-lines:{rule['path']}",
                        path=rule["path"],
                        line=0,
                        message=f"{n} dòng > giới hạn {rule['max']}",
                        fix=rule.get("fix", "Rút gọn hoặc chuyển nội dung sang rule/doc riêng"),
                    )
                )
    decisions = root / "docs" / "decisions"
    index = decisions / "README.md"
    if decisions.exists() and index.exists():
        index_text = index.read_text(encoding="utf-8")
        tracked_set = set(tracked)
        for adr_file in sorted(decisions.iterdir()):
            if f"docs/decisions/{adr_file.name}" not in tracked_set:
                continue
            m = _ADR_FILE.match(adr_file.name)
            if not m or m.group(1) == "0000":
                continue
            rel = f"docs/decisions/{adr_file.name}"
            if f"({adr_file.name})" not in index_text:
                out.append(
                    Violation(
                        check="doc_limits",
                        rule="adr-index",
                        path=rel,
                        line=0,
                        message="ADR không có trong bảng docs/decisions/README.md",
                        fix="Thêm 1 dòng vào bảng chỉ mục",
                    )
                )
            body = adr_file.read_text(encoding="utf-8")
            for label in ("**Trạng thái**", "**Ngày**"):
                if label not in body:
                    out.append(
                        Violation(
                            check="doc_limits",
                            rule="adr-fields",
                            path=rel,
                            line=0,
                            message=f"thiếu trường {label}",
                            fix="Theo docs/decisions/0000-template.md",
                        )
                    )
    return out


# --- 6. count_fact --------------------------------------------------------------------


def collected_test_count(root: Path, ignore: list[str] | None = None) -> int | None:
    """`ignore`: file test chưa track (chế độ commit) — không thuộc commit nên không đếm."""
    extra = [f"--ignore={p}" for p in ignore or []]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *extra],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    m = re.search(r"(\d+) tests? collected", result.stdout)
    return int(m.group(1)) if m else None


def check_count_facts(
    root: Path, files: list[str], cfg: Config, actual: int | None
) -> list[Violation]:
    out: list[Violation] = []
    if actual is None or not cfg.count_facts:
        return out
    for rule in cfg.count_facts:
        pattern = re.compile(rule["pattern"])
        for rel in files:
            if _matches(rel, cfg.exclude) or not _matches(rel, rule.get("paths", ["**"])):
                continue
            text = read_text(root / rel)
            if text is None:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines):
                for m in pattern.finditer(line):
                    if int(m.group("n")) != actual and not _allowed_inline(lines, i, rule["id"]):
                        out.append(
                            Violation(
                                check="count_fact",
                                rule=rule["id"],
                                path=rel,
                                line=i + 1,
                                message=f"ghi {m.group('n')} test nhưng thực tế thu thập {actual}",
                                fix=f"Cập nhật thành {actual}",
                            )
                        )
    return out


# --- 7. ui_contract (ADR-0020) --------------------------------------------------------

_CONTRACT_MARK = re.compile(r"Cập nhật tới:\s*ADR-(\d{4})")
# Dòng bảng: id `UI-<ADR 4 số>-slug` hoặc `UI-L<yyyymmdd>-slug` (quyết định trong legacy-log)
_CONTRACT_ROW = re.compile(r"^\|\s*(UI-(\d{4}|L\d{8})-[A-Za-z0-9-]+)\s*\|")
_RULE_REF = re.compile(r"`([A-Z][A-Za-z0-9]*-[\w-]+)`")
_TEST_REF = re.compile(
    r"\b(test_\w+)"
)  # mọi tên test trong cột D (mã luật không bắt đầu bằng test_)
_TEST_DEF = re.compile(r"^\s*(?:async\s+)?def (test_\w+)\(", re.MULTILINE)
_UI_IMPACT = re.compile(r"^###\s+Hệ quả UI\b", re.MULTILINE)
# Tách ô theo `|` chưa escape — `\|` trong ô (VD kiểu TS `"live" \| "next"`) không phải ranh giới
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
# "| id | ADR | A | B | C | D | E |" → 9 mảnh (rỗng 2 đầu); mảnh 6 = cột D (Kiểm bằng)
_CONTRACT_CELLS = 9
_CHECK_COLUMN = 6


def _adr_numbers(tracked: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for rel in tracked:
        head, _, name = rel.rpartition("/")
        m = _ADR_FILE.match(name)
        if head == "docs/decisions" and m and m.group(1) != "0000":
            out[int(m.group(1))] = rel
    return out


def _rule_ids(cfg: Config) -> set[str]:
    return {str(r["id"]) for r in cfg.forbid + cfg.stale_assets + cfg.count_facts if "id" in r}


def _test_names(root: Path, tracked: list[str]) -> set[str]:
    names: set[str] = set()
    for rel in tracked:
        if rel.startswith("tests/") and rel.endswith(".py"):
            names.update(_TEST_DEF.findall(read_text(root / rel) or ""))
    return names


def check_ui_contract(root: Path, cfg: Config, tracked: list[str]) -> list[Violation]:
    out: list[Violation] = []
    if not cfg.ui_contract:
        return out
    adrs = _adr_numbers(tracked)

    def v(rule: str, path: str, line: int, message: str, fix: str) -> None:
        out.append(Violation("ui_contract", rule, path, line, message, fix, "0020"))

    # ADR mới phải tự nói nó buộc UI đổi gì (hoặc "không có hệ quả UI")
    if cfg.ui_impact_from:
        for n, rel in sorted(adrs.items()):
            body = unicodedata.normalize(
                "NFC", read_text(root / rel) or ""
            )  # bộ gõ có thể sinh NFD
            if n >= cfg.ui_impact_from and not _UI_IMPACT.search(body):
                v(
                    "adr-ui-impact",
                    rel,
                    0,
                    "thiếu mục '### Hệ quả UI'",
                    "Thêm mục theo docs/decisions/0000-template.md (kể cả 'không có hệ quả UI')",
                )
    raw = read_text(root / cfg.ui_contract)
    text = unicodedata.normalize("NFC", raw) if raw is not None else None
    if text is None:
        if adrs:
            v("ui-contract-missing", cfg.ui_contract, 0, "chưa có hợp đồng UI", "Tạo file")
        return out
    mark = _CONTRACT_MARK.search(text)
    if mark is None:
        v(
            "ui-contract-mark",
            cfg.ui_contract,
            0,
            "thiếu mốc 'Cập nhật tới: ADR-NNNN'",
            "Ghi mốc ở đầu file",
        )
        return out
    upto = int(mark.group(1))
    newer = [n for n in adrs if n > upto]
    if newer:
        v(
            "ui-contract-stale",
            cfg.ui_contract,
            text.count("\n", 0, mark.start()) + 1,
            f"ADR-{max(newer):04d} mới hơn mốc 'Cập nhật tới: ADR-{upto:04d}'",
            "Thêm dòng cho ADR mới (theo mục 'Hệ quả UI' của nó) rồi nâng mốc",
        )
    rule_ids = _rule_ids(cfg)
    tests = _test_names(root, tracked)
    seen: dict[str, int] = {}
    covered: set[int] = set()
    for i, line in enumerate(text.splitlines(), start=1):
        m = _CONTRACT_ROW.match(line)
        if not m:
            continue
        row_id, ref = m.group(1), m.group(2)
        if row_id in seen:
            v(
                "ui-contract-dup-id",
                cfg.ui_contract,
                i,
                f"id {row_id} trùng dòng {seen[row_id]}",
                "Mỗi id chỉ dùng 1 lần, không tái dùng",
            )
        seen[row_id] = i
        if ref.isdigit():
            if int(ref) not in adrs:
                v(
                    "ui-contract-unknown-adr",
                    cfg.ui_contract,
                    i,
                    f"ADR-{ref} không tồn tại (hoặc chưa `git add`)",
                    "Sửa số ADR trong id",
                )
            covered.add(int(ref))
        cells = _CELL_SPLIT.split(line)
        if len(cells) != _CONTRACT_CELLS:
            v(
                "ui-contract-malformed-row",
                cfg.ui_contract,
                i,
                f"{len(cells) - 2} cột thay vì 7 — cột D không kiểm được",
                "Đủ 7 cột; '|' bên trong ô viết là '\\|'",
            )
            continue
        check_cell = cells[_CHECK_COLUMN]
        for rid in _RULE_REF.findall(check_cell):
            if rid not in rule_ids:
                v(
                    "ui-contract-unknown-rule",
                    cfg.ui_contract,
                    i,
                    f"luật {rid} không có trong {INVARIANTS_PATH}",
                    "Sửa mã luật hoặc ghi manual",
                )
        for name in _TEST_REF.findall(check_cell):
            if name not in tests:
                v(
                    "ui-contract-unknown-test",
                    cfg.ui_contract,
                    i,
                    f"không có test {name} (hoặc file test chưa `git add`)",
                    "Sửa tên test hoặc ghi manual",
                )
    for n in sorted(adrs):
        if n <= upto and n not in covered:
            v(
                "ui-contract-missing-adr",
                cfg.ui_contract,
                0,
                f"chưa có dòng nào cho ADR-{n:04d}",
                "Thêm ít nhất 1 dòng (B = 'không có hệ quả UI' nếu không có)",
            )
    return out


# --- 8. ref_anchor --------------------------------------------------------------------

# Tham chiếu code trong docs (ADR-0033): `path:N#Tên`, `path:N-M#Tên`, hoặc `:N#Tên` (cùng file
# với file nhắc gần nhất trước nó trong tài liệu). Số dòng trôi mỗi khi code thêm/bớt dòng; tên neo
# cho máy biết dòng đó PHẢI chứa gì, và cho `--fix-refs` tìm lại chỗ mới.
REF_RULE = "ref-anchor"
_REF = re.compile(
    # Số dòng: chữ số ASCII, không 0 đứng đầu (`\d` còn khớp chữ số Unicode như `٢`) — `:03`, `:1٢`
    # rơi về `_LOOSE_REF` → báo "không đọc được"; nhờ vậy chuỗi gốc luôn chứa đúng `:{int(a)}`
    r"^(?P<path>[\w./()\[\]-]+\.\w+)?:(?P<a>[1-9][0-9]*)(?:-(?P<b>[1-9][0-9]*))?"
    r"(?:#(?P<anchor>[A-Za-z_$][\w$-]*))?$"
)
# Ranh giới tên neo: không dính chữ/số/_/$/- hai bên (`cta` không khớp trong `ADR0032-cta-no-logo`)
_ANCHOR_EDGE = r"[\w$-]"


# Trông như tham chiếu code (`x.py:3`, `x.py:L3`, `x.py:3 #f`, `x.py:3#a.b`, `:3`): `_REF` không đọc
# được thì BÁO LỖI, không bỏ qua — bộ kiểm không được im lặng khi gặp thứ nó không hiểu
_LOOSE_REF = re.compile(r"^(?:[\w./()\[\]-]+\.[A-Za-z]\w*)?:L?\d")
# `:` + chỉ chữ số (VD phút `:05`, khoảng `:05-07`): không ngữ cảnh file thì không phải tham chiếu,
# xử lý như `:15` / `:15-17`
_BARE_NUMBER = re.compile(r"^:[0-9]+(?:-[0-9]+)?$")
# Tên file / đường dẫn nhắc trong câu (không số dòng) — ngữ cảnh cho `:N` trần phía sau
_FILE_LIKE = re.compile(r"^[\w./()\[\]-]+\.[A-Za-z]\w*$")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
# Đầu 1 khối markdown mới (mục danh sách, tiêu đề, dòng bảng): code span và ngữ cảnh `:N` không vắt
# qua ranh giới khối; trong 1 khối thì vắt dòng được — gần CommonMark (không xử lý chú thích HTML,
# khối code thụt lề)
_BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}(?:\s|$)|\|)")
# Code span: mở và đóng bằng chuỗi backtick CÙNG độ dài (``a`b`` là 1 span), như CommonMark
_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)


@dataclass(frozen=True)
class CodeRef:
    line: int  # chỉ số dòng 0-based trong tài liệu
    start: int  # vị trí nội dung trong backtick (không gồm dấu `)
    end: int
    file: str
    a: int
    b: int
    anchor: str | None
    error: str | None = None  # không đọc được / không biết file → vi phạm, không bỏ qua


def _file_index(known: list[str]) -> tuple[frozenset[str], dict[str, list[str]]]:
    by_base: dict[str, list[str]] = {}
    for f in known:
        by_base.setdefault(f.rsplit("/", 1)[-1], []).append(f)
    return frozenset(known), by_base


def _ref_file_candidates(
    name: str, known: frozenset[str], by_base: dict[str, list[str]]
) -> list[str]:
    """Đường dẫn đầy đủ, hoặc mọi file có tên ngắn / đuôi đường dẫn khớp (VD `LandingHero.tsx`)."""
    if name in known:
        return [name]
    base = name.rsplit("/", 1)[-1]
    return [f for f in by_base.get(base, []) if f == name or f.endswith("/" + name)]


def _md_blocks(lines: list[str]) -> list[list[int]]:
    """Chỉ số dòng theo từng khối markdown (đoạn văn, mục danh sách, dòng bảng); bỏ code rào."""
    blocks: list[list[int]] = []
    current: list[int] = []
    fenced = False
    for i, raw in enumerate(lines):
        line = raw.rstrip("\r")
        if _FENCE.match(line) or fenced or not line.strip() or _BLOCK_START.match(line):
            if current:
                blocks.append(current)
            current = []
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced or not line.strip():
            continue
        current.append(i)
    if current:
        blocks.append(current)
    return blocks


def iter_code_refs(
    lines: list[str],
    known: frozenset[str],
    by_base: dict[str, list[str]],
    public: bool = True,  # tài liệu ngoài `.claude/` — không được trỏ vào harness riêng tư
) -> list[CodeRef]:
    refs: list[CodeRef] = []
    for block in _md_blocks(lines):
        starts: list[int] = []  # vị trí đầu mỗi dòng trong văn bản ghép của khối
        pos = 0
        for i in block:
            starts.append(pos)
            pos += len(lines[i].rstrip("\r")) + 1
        text = "\n".join(lines[i].rstrip("\r") for i in block)
        context: str | None = None  # file nhắc gần nhất trong khối — `:N` trần thuộc file này
        for m in _SPAN.finditer(text):
            span, offset = m.group(2), m.start(2)
            if "\n" in span:
                continue  # span vắt dòng không phải tham chiếu, nhưng vẫn giữ đúng cặp backtick
            if len(span) > 2 and span[0] == span[-1] == " " and span.strip():
                span, offset = span[1:-1], offset + 1  # `` `x` `` — bỏ 1 dấu cách mỗi bên
            k = max(j for j, s in enumerate(starts) if s <= offset)
            line, col = block[k], offset - starts[k]
            r = _REF.match(span)
            if r is None:
                if context is None and _BARE_NUMBER.match(span):
                    continue  # `:05` trần không ngữ cảnh — cùng cách xử lý `:15` ở dưới
                if _LOOSE_REF.match(span):
                    refs.append(_bad(line, col, span, f"không đọc được tham chiếu `{span}`"))
                elif " " not in span and _FILE_LIKE.match(_clean_candidate(span) or ""):
                    cands = _ref_file_candidates(_clean_candidate(span) or "", known, by_base)
                    if cands:  # trông như tên file mà không có file (VD `np.mean`) → giữ ngữ cảnh
                        context = cands[0] if len(cands) == 1 else None
                continue
            path = r.group("path")
            if path:
                cands = _ref_file_candidates(path, known, by_base)
                context = cands[0] if len(cands) == 1 else None
                if len(cands) > 1:
                    refs.append(_bad(line, col, span, f"`{path}` khớp {len(cands)} file"))
                    continue
                if context is None:
                    # Đường dẫn đủ không có → dead_path đã báo; tên ngắn không có → báo ở đây.
                    # Riêng `.claude/…`: dead_path --all cho qua (file harness có trên máy, hoặc
                    # known_untracked) nên báo ở đây — tài liệu công khai không trỏ vào harness
                    if public and path.startswith(HARNESS_DIR + "/"):
                        message = f"không có `{path}` — tài liệu công khai không trỏ vào harness"
                        refs.append(_bad(line, col, span, message))
                    elif "/" not in path and _FILE_LIKE.match(path):
                        refs.append(_bad(line, col, span, f"không có file `{path}`"))
                    continue  # còn lại không phải tham chiếu code (VD `127.0.0.1:8000`)
            elif context is None:
                if r.group("anchor"):
                    refs.append(_bad(line, col, span, f"`{span}` không biết thuộc file nào"))
                continue  # `:N` trần không ngữ cảnh, không tên neo — không phải tham chiếu (VD giờ)
            a = int(r.group("a"))
            refs.append(
                CodeRef(
                    line,
                    col,
                    col + len(span),
                    context,
                    a,
                    int(r.group("b") or a),
                    r.group("anchor"),
                )
            )
    return refs


def _bad(line: int, col: int, span: str, error: str) -> CodeRef:
    return CodeRef(line, col, col + len(span), "", 0, 0, None, error)


def _ref_allowed(lines: list[str], idx: int) -> bool:
    """Allow `ref-anchor` trên chính dòng đó, hoặc ở dòng trước khi dòng trước CHỈ có chú thích —
    dấu allow cuối 1 dòng lịch sử không được miễn luôn tham chiếu hiện hành ở dòng sau."""
    if _allowed_inline(lines[idx : idx + 1], 0, REF_RULE):
        return True
    prev = lines[idx - 1].strip() if idx > 0 else ""
    only_comment = prev.startswith("<!--") and prev.endswith("-->")
    return only_comment and _allowed_inline([prev], 0, REF_RULE)


def _has_anchor(text: str, anchor: str) -> bool:
    return re.search(rf"(?<!{_ANCHOR_EDGE}){re.escape(anchor)}(?!{_ANCHOR_EDGE})", text) is not None


def locate_anchor(code: list[str], anchor: str) -> int | None:
    """Dòng (1-based) của tên neo nếu xác định được duy nhất: ưu tiên dòng ĐỊNH NGHĨA (def/class/
    function/const/…, hoặc `tên =` / `tên:` đầu dòng); không thì dòng duy nhất chứa tên. Nhiều chỗ
    → None: để người chọn, không đoán (dời nhầm rồi thì kiểm tra cũng qua)."""
    a = re.escape(anchor)
    definition = re.compile(
        rf"\b(?:def|class|function|const|let|var|interface|type|enum)\s+{a}(?!{_ANCHOR_EDGE})"
        rf"|^\s*[\"']?{a}[\"']?\s*[:=]"
    )
    hits = [n for n, text in enumerate(code, 1) if _has_anchor(text, anchor)]
    defs = [n for n in hits if definition.search(code[n - 1])]
    if len(defs) == 1:
        return defs[0]
    return hits[0] if len(hits) == 1 else None


def _ref_problem(ref: CodeRef, code: list[str]) -> tuple[str, str] | None:
    """(thông điệp, cách sửa) nếu tham chiếu hỏng; None nếu đúng."""
    if ref.error is not None:
        return (
            ref.error,
            "Ghi `path:N#Tên` (ADR-0033); tên file ngắn chỉ dùng khi repo có đúng 1 file trùng tên",
        )
    shown = f"{ref.file}:{ref.a}" + (f"-{ref.b}" if ref.b != ref.a else "")
    if ref.anchor is None:
        return (
            f"tham chiếu {shown} thiếu tên neo",
            f"Ghi `…:{ref.a}#Tên` — Tên là hàm/biến/khoá phải có ở dòng đó (ADR-0033)",
        )
    if ref.b < ref.a or ref.b > len(code):
        return (f"{shown} quá cuối file ({len(code)} dòng)", _fix_hint(ref, code))
    if not any(_has_anchor(text, ref.anchor) for text in code[ref.a - 1 : ref.b]):
        return (f"{shown} không còn chứa `{ref.anchor}`", _fix_hint(ref, code))
    return None


def _fix_hint(ref: CodeRef, code: list[str]) -> str:
    assert ref.anchor is not None
    found = locate_anchor(code, ref.anchor)
    if found is not None:
        return f"`{ref.anchor}` giờ ở dòng {found} — chạy `check --fix-refs` để tự dời số"
    return f"`{ref.anchor}` không có hoặc có ở nhiều chỗ trong file — sửa tay số dòng hoặc tên neo"


def _code_lines(root: Path, rel: str, cache: dict[str, list[str] | None]) -> list[str] | None:
    if rel not in cache:
        text = read_text(root / rel)
        cache[rel] = text.split("\n") if text is not None else None
    return cache[rel]


def check_ref_anchors(
    root: Path,
    files: list[str],
    known: list[str],
    cfg: Config,
    harness: Sequence[str] = (),
) -> list[Violation]:
    """`known` = file đích của tài liệu công khai; `harness` = file harness trên máy, chỉ là đích
    của tài liệu nằm TRONG harness. Tài liệu công khai không trỏ được vào harness riêng tư (clone
    công khai không có nó) — nhờ vậy tên file ngắn phân giải như nhau ở `--all`, `--commit`, CI."""
    public = _file_index(known)
    listed = set(known)
    private = _file_index(list(known) + [f for f in harness if f not in listed])
    cache: dict[str, list[str] | None] = {}
    out: list[Violation] = []
    for rel in files:
        if not rel.endswith(".md") or _matches(rel, cfg.exclude):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        lines = text.split("\n")
        in_harness = rel.startswith(HARNESS_DIR + "/")
        index, by_base = private if in_harness else public
        for ref in iter_code_refs(lines, index, by_base, public=not in_harness):
            code = [] if ref.error else _code_lines(root, ref.file, cache)
            if code is None:
                continue  # file nhị phân / quá lớn — không phải code đọc được
            problem = _ref_problem(ref, code)
            if problem is None or _ref_allowed(lines, ref.line):
                continue
            out.append(
                Violation(
                    check="ref_anchor",
                    rule=REF_RULE,
                    path=rel,
                    line=ref.line + 1,
                    message=problem[0],
                    fix=problem[1],
                    adr="0033",
                )
            )
    return out


def _map_line(opcodes: Sequence[tuple[str, int, int, int, int]], n: int) -> int | None:
    """Dòng n (1-based) của bản cũ ứng với dòng nào ở bản mới — chỉ khi nằm trong đoạn không đổi."""
    for tag, i1, i2, j1, _j2 in opcodes:
        if i1 <= n - 1 < i2:
            return j1 + (n - 1 - i1) + 1 if tag == "equal" else None
    return None


_HeadDiff = tuple[list[str], difflib.SequenceMatcher[str]] | None


def _diff_target(
    root: Path, ref: CodeRef, code: list[str], cache: dict[str, _HeadDiff]
) -> tuple[int, int] | None:
    """Vị trí mới theo diff file code so với HEAD: tham chiếu đúng ở HEAD thì dời đúng theo số dòng
    code đã xê dịch — giữ dòng tác giả chọn, kể cả dòng DÙNG tên chứ không phải định nghĩa."""
    assert ref.anchor is not None
    if ref.file not in cache:
        old = _git(root, "show", f"HEAD:{ref.file}")
        # Bỏ "\r": file trên đĩa Windows có thể là CRLF, bản trong git là LF
        old_lines = [t.rstrip("\r") for t in old.split("\n")]
        new_lines = [t.rstrip("\r") for t in code]
        cache[ref.file] = (
            None
            if not old
            else (old_lines, difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False))
        )
    entry = cache[ref.file]
    if entry is None:
        return None
    old_lines, matcher = entry
    if ref.b > len(old_lines) or not any(
        _has_anchor(t, ref.anchor) for t in old_lines[ref.a - 1 : ref.b]
    ):
        return None  # ở HEAD đã lệch → diff không nói được tác giả định trỏ đâu
    opcodes = matcher.get_opcodes()
    a = _map_line(opcodes, ref.a)
    if a is None:
        return None
    b = _map_line(opcodes, ref.b) or a + ref.b - ref.a
    if not any(_has_anchor(t, ref.anchor) for t in code[a - 1 : b]):
        return None
    return a, b


def fix_ref_anchors(root: Path, files: list[str], known: list[str], cfg: Config) -> int:
    """Dời số dòng của tham chiếu có tên neo: theo diff file code so với HEAD nếu được, không thì về
    chỗ mới của Tên khi xác định duy nhất. Bỏ qua dòng có `allow ref-anchor` (tham chiếu lịch sử
    cố ý trỏ code cũ). Trả số tham chiếu đã dời."""
    index, by_base = _file_index(known)
    cache: dict[str, list[str] | None] = {}
    head: dict[str, _HeadDiff] = {}
    moved = 0
    for rel in files:
        if not rel.endswith(".md") or _matches(rel, cfg.exclude):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        lines = text.split("\n")
        changed = False
        # Từ phải sang trái để vị trí các tham chiếu còn lại trên cùng dòng không đổi
        for ref in sorted(iter_code_refs(lines, index, by_base), key=lambda r: (r.line, -r.start)):
            if ref.error or ref.anchor is None or _ref_allowed(lines, ref.line):
                continue
            code = _code_lines(root, ref.file, cache)
            if code is None or _ref_problem(ref, code) is None:
                continue
            target = _diff_target(root, ref, code, head)
            if target is None:
                found = locate_anchor(code, ref.anchor)
                if found is None:
                    continue
                target = (found, found + ref.b - ref.a)
            old = lines[ref.line][ref.start : ref.end]
            prefix = old[: old.index(f":{ref.a}")]
            span = f"{target[0]}" if target[1] == target[0] else f"{target[0]}-{target[1]}"
            new = f"{prefix}:{span}#{ref.anchor}"
            lines[ref.line] = lines[ref.line][: ref.start] + new + lines[ref.line][ref.end :]
            moved += 1
            changed = True
        if changed:
            (root / rel).write_bytes("\n".join(lines).encode("utf-8"))
    return moved


# --- Chạy -----------------------------------------------------------------------------


def check_harness_not_tracked(paths: list[str]) -> list[Violation]:
    """Harness riêng tư không được vào repo public — `git add -f` vượt `.gitignore` (ADR-0027)."""
    return [
        Violation(
            check="harness",
            rule="ADR0027-harness-not-tracked",
            path=p,
            line=0,
            message="harness .claude/ riêng tư bị track/stage trong repo public",
            fix=f"git rm --cached {p} — sửa harness trong kho riêng (docs/claude/git-workflow.md)",
            adr="0027",
        )
        for p in paths
        if p.startswith(HARNESS_DIR + "/")
    ]


def run(root: Path, mode: str, with_pytest: bool = True) -> list[Violation]:
    cfg = load_config(root)
    tracked = tracked_files(root)
    staged = staged_files(root) if mode in ("staged", "commit") else None
    if mode == "staged" and staged is not None:
        files = staged
    elif mode == "all":
        files = tracked + untracked_files(root)
        listed = set(files)  # checkout cũ còn track/chưa ignore `.claude/` → không quét 2 lần
        files += [f for f in harness_files(root) if f not in listed]
    else:  # commit: file chưa track không thuộc commit (pre-commit không cất chúng đi)
        files = tracked
    # --all: thêm file chưa track; file harness trên máy chỉ là đích của tài liệu harness
    known = tracked + untracked_files(root) if mode == "all" else tracked
    harness = harness_files(root) if mode == "all" else []
    violations = check_forbid(root, files, cfg)
    violations += check_ref_anchors(root, files, known, cfg, harness)
    # Cả --all: CI chỉ chạy --all — lưới thứ hai khi commit lọt pre-commit
    # (--no-verify, clone chưa cài hook)
    violations += check_harness_not_tracked((staged or []) if mode == "staged" else tracked)
    violations += check_dead_paths(root, files, tracked, cfg, strict=mode == "commit")
    violations += check_readme_sync(root, staged)
    violations += check_stale_assets(root, cfg)
    violations += check_doc_limits(root, cfg, tracked)
    violations += check_ui_contract(root, cfg, tracked)
    if mode in ("all", "commit") and with_pytest:
        ignore = None
        if mode == "commit":  # pre-commit không cất file chưa track → loại khỏi lần đếm
            ignore = [f for f in untracked_files(root) if f.startswith("tests/")]
        violations += check_count_facts(root, files, cfg, collected_test_count(root, ignore))
    return violations


def _format_group(violations: list[Violation]) -> list[str]:
    lines: list[str] = []
    by_path: dict[str, list[Violation]] = {}
    for v in violations:
        by_path.setdefault(v.path, []).append(v)
    for path in sorted(by_path):
        lines.append(f"\n{path}")
        for v in sorted(by_path[path], key=lambda x: x.line):
            where = f":{v.line}" if v.line else ""
            adr = f" [ADR-{v.adr}]" if v.adr and v.adr[:1].isdigit() else ""
            lines.append(f"  {where or '-'} {v.rule}{adr} — {v.message}")
            if v.fix:
                lines.append(f"      → {v.fix}")
    return lines


def format_report(violations: list[Violation]) -> str:
    errors = errors_only(violations)
    warnings = [v for v in violations if v.severity != "error"]
    lines = [f"consistency: {len(errors)} vi phạm" if errors else "consistency: 0 vi phạm ✓"]
    lines += _format_group(errors)
    if errors:
        lines.append(
            f"\nNgoại lệ có chủ đích: thêm '{ALLOW_MARK} <rule-id>' trên dòng đó hoặc dòng trước."
        )
        if any(v.rule == REF_RULE for v in errors):
            # `_ref_allowed`: allow cuối 1 dòng có chữ không miễn tham chiếu ở dòng sau
            lines.append(
                f"Riêng {REF_RULE}: allow ở dòng trước chỉ tính khi dòng đó CHỈ có chú thích "
                f"<!-- {ALLOW_MARK} {REF_RULE} — lý do -->."
            )
    if warnings:
        lines.append(
            f"\nCảnh báo mockup (không chặn commit — Claude Design sửa, ghi audit, ADR-0020): "
            f"{len(warnings)}"
        )
        lines += _format_group(warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="toàn repo, kể cả file chưa track")
    group.add_argument("--staged", action="store_true", help="chỉ file đang stage")
    group.add_argument(
        "--commit", action="store_true", help="pre-commit: toàn repo + README theo file stage"
    )
    parser.add_argument(
        "--fix-refs",
        action="store_true",
        help="dời số dòng của tham chiếu `path:N#Tên` về chỗ mới của Tên, rồi kiểm như --all",
    )
    parser.add_argument("--json", action="store_true", help="xuất JSON")
    parser.add_argument("--no-pytest", action="store_true", help="bỏ kiểm tra số test")
    parser.add_argument(
        "--count",
        action="store_true",
        help="chỉ in số vi phạm (dòng 2 'mockup-warnings: N' khi có cảnh báo mockup)",
    )
    # Trước parse_args: --help in tiếng Việt, cp1252 mặc định của Windows sẽ crash
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    args = parser.parse_args(argv)
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip() or ".")
    mode = "staged" if args.staged else "commit" if args.commit else "all"
    if args.fix_refs and mode != "all":
        parser.error("--fix-refs chỉ chạy với --all (sửa file trên đĩa)")
    try:
        if args.fix_refs:
            known = tracked_files(root) + untracked_files(root)
            moved = fix_ref_anchors(root, known, known, load_config(root))
            # stderr: không làm hỏng đầu ra --json / --count
            print(f"ref_anchor: đã dời số dòng của {moved} tham chiếu", file=sys.stderr)
        violations = run(root, mode, with_pytest=not (args.no_pytest or args.count))
    except (tomllib.TOMLDecodeError, re.error, KeyError) as exc:
        # Sổ luật hỏng phải chặn commit với thông báo rõ ràng, không phải traceback
        print(f"consistency: sổ luật {INVARIANTS_PATH} không hợp lệ — {type(exc).__name__}: {exc}")
        return 2
    errors = errors_only(violations)
    if args.count:
        print(len(errors))
        if len(violations) > len(errors):
            print(f"mockup-warnings: {len(violations) - len(errors)}")
    elif args.json:
        print(json.dumps([asdict(v) for v in violations], ensure_ascii=False, indent=2))
    else:
        print(format_report(violations))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
