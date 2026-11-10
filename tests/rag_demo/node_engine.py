"""Chạy engine TypeScript của demo RAG bằng node, không bundler (ADR-0037: sản phẩm là TS).

Test Python chỉ là bài giải mẫu; mỗi file test viết một driver `.mjs` nhỏ gọi đúng các module
`src/dashboard/src/lib/ragDemo/*.ts`, truyền ca thử qua JSON và đọc kết quả JSON.
"""

import functools
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ENGINE_DIR = Path(__file__).parents[2] / "src/dashboard/src/lib/ragDemo"
# Node sớm nhất có --experimental-strip-types; thiếu thì test phải hỏng, không được bỏ qua âm thầm
MIN_NODE = (22, 6)


@functools.cache
def node_binary() -> str:
    node = shutil.which("node")
    assert node, "cần node để chạy engine TypeScript"
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True)
    major, minor = version.stdout.strip().lstrip("v").split(".")[:2]
    assert (int(major), int(minor)) >= MIN_NODE, f"cần node >= {MIN_NODE}, có {version.stdout}"
    return node


def run_driver(tmp_path: Path, driver: str, cases: list[dict[str, Any]]) -> list[Any]:
    """Driver nhận argv[2] = URL thư mục engine (kết thúc bằng `/`), argv[3] = file ca thử."""
    node = node_binary()
    script = tmp_path / "driver.mjs"
    script.write_text(driver, encoding="utf-8")
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            node,
            "--experimental-strip-types",
            "--no-warnings",
            str(script),
            ENGINE_DIR.as_uri() + "/",
            str(data),
        ],
        capture_output=True,
        encoding="utf-8",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return list(json.loads(result.stdout))
