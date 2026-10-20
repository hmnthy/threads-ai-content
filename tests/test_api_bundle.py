"""Gói API cho Vercel (ADR-0025, Hệ quả bước 1): hàm Python tối đa 500 MB sau giải nén.

Vercel cài thư viện bằng `uv sync --frozen --no-dev` từ `uv.lock` → bộ cài = `uv export --no-dev`.
Hai điều phải giữ: (1) bộ đó không chứa thư viện của job (nhóm `pipeline` trong `pyproject.toml`),
(2) `import src.main` chạy được khi CHỈ có bộ đó — chặn mọi gói ngoài bộ bằng 1 import hook, nên
import tuỳ chọn (`try: import rich`) rơi về nhánh dự phòng y như trên Vercel.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Danh sách cho phép của `[project].dependencies` — thêm thư viện vào gói Vercel phải là quyết
# định có chủ ý (API cần nó lúc import): sửa danh sách này; thư viện chỉ job dùng →
# `uv add --group pipeline`. Không phải ngưỡng heuristic, chỉ là chốt chặn `uv add` mặc định.
API_DEPENDENCIES = frozenset(
    {"fastapi", "httpx", "numpy", "pydantic", "python-dotenv", "scipy", "tzdata", "uvicorn"}
)
# Thư viện nặng bị kéo gián tiếp bởi nhóm `pipeline` (sentence-transformers → torch, transformers).
TRANSITIVE_HEAVY = ("torch", "transformers")
# Tên module (để kiểm `sys.modules` sau khi import API).
PIPELINE_MODULES = (
    "anthropic",
    "hdbscan",
    "lingua",
    "sklearn",
    "sentence_transformers",
    "torch",
    "transformers",
    "umap",
    "underthesea",
)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(spec: str) -> str:
    return _norm(re.split(r"[=<>!~;\[ ]", spec.strip(), maxsplit=1)[0])


def _pyproject() -> dict[str, object]:
    with (REPO / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)


def _pipeline_group() -> set[str]:
    groups = _pyproject()["dependency-groups"]
    assert isinstance(groups, dict)
    # bỏ mục `{ include-group = … }` (dict), chỉ lấy chuỗi requirement
    return {_requirement_name(s) for s in groups["pipeline"] if isinstance(s, str)}


def _deploy_set() -> set[str]:
    # `UV` do `uv run` đặt — pre-commit gọi thẳng python của .venv, uv có thể không nằm trên PATH
    uv = os.environ.get("UV") or shutil.which("uv")
    assert uv is not None, "cần `uv` (biến UV hoặc PATH) để tính bộ thư viện Vercel cài"
    out = subprocess.run(
        [uv, "export", "--frozen", "--no-dev", "--no-hashes", "--no-header", "--no-annotate"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    names: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            names.add(_requirement_name(line))
    return names


def test_project_dependencies_are_only_what_the_api_needs() -> None:
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    assert {_requirement_name(s) for s in project["dependencies"]} == API_DEPENDENCIES


def test_deploy_set_excludes_pipeline_libraries() -> None:
    deploy = _deploy_set()
    pipeline = _pipeline_group()
    # kiểm chính bộ phân tích: thiếu gói chắc chắn có → parse sai, phép thử dưới vô nghĩa
    assert deploy >= API_DEPENDENCIES
    assert {"anthropic", "lingua-language-detector", "sentence-transformers"} <= pipeline
    assert sorted((pipeline | set(TRANSITIVE_HEAVY)) & deploy) == []


_IMPORT_WITH_ONLY_DEPLOY_SET = """
import importlib.metadata as md
import json
import re
import sys

allowed = set(json.loads(sys.argv[1]))
owners = md.packages_distributions()


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


class OnlyDeploySet:
    def find_spec(self, name, path=None, target=None):
        top = name.partition(".")[0]
        dists = owners.get(top)
        # stdlib, code của repo, module nội bộ không thuộc distribution nào (VD _cython_*)
        if top in sys.stdlib_module_names or top == "src" or not dists:
            return None
        if any(norm(d) in allowed for d in dists):
            return None
        raise ModuleNotFoundError(f"not in the Vercel bundle: {name}", name=name)


sys.meta_path.insert(0, OnlyDeploySet())
import src.main  # noqa: E402,F401

print(json.dumps(sorted(sys.modules)))
"""


def test_api_imports_with_only_deploy_set() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _IMPORT_WITH_ONLY_DEPLOY_SET, json.dumps(sorted(_deploy_set()))],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    loaded = json.loads(proc.stdout)
    assert [m for m in loaded if m.partition(".")[0] in PIPELINE_MODULES] == []
