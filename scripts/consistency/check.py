"""Cảnh sát nhất quán (tầng 1): kiểm repo có khớp các quyết định đã chốt không.

Luật nằm ở `docs/decisions/invariants.toml` — mỗi luật gắn với 1 ADR (hoặc 1 phát hiện
có ngày). Script chỉ dùng thư viện chuẩn để chạy được ở pre-commit, hook và CI.

Các kiểm tra:
1. forbid       — mẫu (regex) lỗi thời bị cấm, trừ vùng `allow` và ngoại lệ có chú thích
2. dead_path    — đường dẫn trong backtick / link markdown phải tồn tại (trừ planned/untracked)
3. readme_sync  — 3 README (EN/VI/FR) cùng cấu trúc; sửa 1 bản phải sửa cả 3 (chế độ --staged)
4. stale_asset  — file nhị phân phải được làm lại sau commit tạo ADR làm nó lỗi thời
5. doc_limits   — giới hạn số dòng (CLAUDE.md, status.md) + chỉ mục ADR đầy đủ
6. count_fact   — số test ghi trong docs khớp số test thật (chỉ --all)

Ngoại lệ có dấu vết: chú thích `consistency: allow <rule-id>` trên cùng dòng hoặc dòng
ngay trước. Dùng:  uv run python -m scripts.consistency.check --all [--json]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import posixpath
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

INVARIANTS_PATH = "docs/decisions/invariants.toml"
README_FILES = ("README.md", "README.vi.md", "README.fr.md")
ALLOW_MARK = "consistency: allow"

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


@dataclass
class Config:
    exclude: list[str] = field(default_factory=list)
    dead_path_exclude: list[str] = field(default_factory=list)
    planned_paths: list[str] = field(default_factory=list)
    known_untracked: list[str] = field(default_factory=list)
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
        forbid=data.get("forbid", []),
        stale_assets=data.get("stale_asset", []),
        max_lines=data.get("max_lines", []),
        count_facts=data.get("count_fact", []),
    )


def _matches(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.stdout


def tracked_files(root: Path) -> list[str]:
    return [p for p in _git(root, "ls-files").splitlines() if p]


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
        if _matches(rel, cfg.exclude):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        for rule, pattern in compiled:
            if _matches(rel, rule.get("allow", [])):
                continue
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


def _path_ok(root: Path, rel_path: str, cfg: Config) -> bool:
    norm = rel_path.rstrip("/")
    if (root / norm).exists():
        return True
    # Tham chiếu kiểu module Python: src/api/endpoints.get_x → src/api/endpoints.py
    head, _, last = norm.rpartition("/")
    if "." in last and (root / head / (last.split(".", 1)[0] + ".py")).exists():
        return True
    return _matches(norm, cfg.planned_paths) or _matches(norm, cfg.known_untracked)


def check_dead_paths(
    root: Path, files: list[str], tracked: list[str], cfg: Config
) -> list[Violation]:
    tops = _top_level_names(root, tracked, cfg)
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
                if _path_ok(root, rel_target, cfg):
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


def _first_commit_time(root: Path, pattern: str) -> int | None:
    out = _git(root, "log", "--diff-filter=A", "--format=%ct", "--", pattern).split()
    return int(out[-1]) if out else None


def _last_commit_time(root: Path, path: str) -> int | None:
    out = _git(root, "log", "-1", "--format=%ct", "--", path).strip()
    return int(out) if out else None


def check_stale_assets(root: Path, cfg: Config) -> list[Violation]:
    out: list[Violation] = []
    for rule in cfg.stale_assets:
        path = rule["path"]
        adr = str(rule["adr"])
        adr_time = _first_commit_time(root, f"docs/decisions/{adr}-*.md")
        if adr_time is None:
            continue  # ADR chưa commit — chưa có mốc để so
        if _git(root, "status", "--porcelain", "--", path).strip():
            continue  # đang được làm lại trong working tree / staged
        asset_time = _last_commit_time(root, path)
        if asset_time is None or asset_time <= adr_time:
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


def collected_test_count(root: Path) -> int | None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
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


# --- Chạy -----------------------------------------------------------------------------


def run(root: Path, mode: str, with_pytest: bool = True) -> list[Violation]:
    cfg = load_config(root)
    tracked = tracked_files(root)
    staged = staged_files(root) if mode == "staged" else None
    files = staged if staged is not None else tracked
    violations = check_forbid(root, files, cfg)
    violations += check_dead_paths(root, files, tracked, cfg)
    violations += check_readme_sync(root, staged)
    violations += check_stale_assets(root, cfg)
    violations += check_doc_limits(root, cfg, tracked)
    if mode == "all" and with_pytest:
        violations += check_count_facts(root, tracked, cfg, collected_test_count(root))
    return violations


def format_report(violations: list[Violation]) -> str:
    if not violations:
        return "consistency: 0 vi phạm ✓"
    lines = [f"consistency: {len(violations)} vi phạm"]
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
    lines.append(
        f"\nNgoại lệ có chủ đích: thêm '{ALLOW_MARK} <rule-id>' trên dòng đó hoặc dòng trước."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="quét toàn bộ file git theo dõi")
    group.add_argument("--staged", action="store_true", help="chỉ file đang stage (pre-commit)")
    parser.add_argument("--json", action="store_true", help="xuất JSON")
    parser.add_argument("--no-pytest", action="store_true", help="bỏ kiểm tra số test")
    parser.add_argument("--count", action="store_true", help="chỉ in số vi phạm")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip() or ".")
    mode = "staged" if args.staged else "all"
    try:
        violations = run(root, mode, with_pytest=not (args.no_pytest or args.count))
    except (tomllib.TOMLDecodeError, re.error, KeyError) as exc:
        # Sổ luật hỏng phải chặn commit với thông báo rõ ràng, không phải traceback
        print(f"consistency: sổ luật {INVARIANTS_PATH} không hợp lệ — {type(exc).__name__}: {exc}")
        return 2
    if args.count:
        print(len(violations))
    elif args.json:
        print(json.dumps([asdict(v) for v in violations], ensure_ascii=False, indent=2))
    else:
        print(format_report(violations))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
