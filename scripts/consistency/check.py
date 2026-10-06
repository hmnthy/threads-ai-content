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

Mockup (`mockup_paths`, của Claude Design) chỉ bị quét bởi luật forbid có `mockups = true`, và
vi phạm ở đó là CẢNH BÁO (severity "warn"): in ra, ghi audit, nhưng không chặn commit (ADR-0020).

Ngoại lệ có dấu vết: chú thích `consistency: allow <rule-id>` trên cùng dòng hoặc dòng
ngay trước. Dùng:  uv run python -m scripts.consistency.check --all [--json]

Chế độ: --all (toàn repo; hook đầu phiên, sweep, CI) · --commit (pre-commit: toàn repo +
luật "3 README sửa cùng nhau" theo file đang stage — ~6 giây) · --staged (chỉ file stage).
Pre-commit quét toàn repo vì luật đếm số / ảnh lỗi thời / đường dẫn chết hỏng do file KHÁC
file đang sửa (VD thêm test làm README ghi sai số test) — chỉ quét file stage thì lọt.
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
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

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
    if "." in last and present(f"{head}/{last.split('.', 1)[0]}.py"):
        return True
    return _matches(norm, cfg.planned_paths) or _matches(norm, cfg.known_untracked)


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


# --- Chạy -----------------------------------------------------------------------------


def run(root: Path, mode: str, with_pytest: bool = True) -> list[Violation]:
    cfg = load_config(root)
    tracked = tracked_files(root)
    staged = staged_files(root) if mode in ("staged", "commit") else None
    if mode == "staged" and staged is not None:
        files = staged
    elif mode == "all":
        files = tracked + untracked_files(root)
    else:  # commit: file chưa track không thuộc commit (pre-commit không cất chúng đi)
        files = tracked
    violations = check_forbid(root, files, cfg)
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
    try:
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
