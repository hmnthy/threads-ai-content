"""Khối `if __name__ == "__main__":` phải là câu lệnh cuối module pipeline — đặt giữa
file thì chạy `python -m` sẽ gọi hàm chưa được định nghĩa (lỗi đã gặp ở ingest.py)."""

import ast
from pathlib import Path

import pytest

PIPELINE = sorted((Path(__file__).resolve().parents[2] / "src" / "pipeline").glob("*.py"))


def _is_main_guard(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )


@pytest.mark.parametrize("path", PIPELINE, ids=lambda p: p.name)
def test_main_guard_is_last_statement(path: Path) -> None:
    body = ast.parse(path.read_text(encoding="utf-8")).body
    guards = [i for i, node in enumerate(body) if _is_main_guard(node)]
    assert all(i == len(body) - 1 for i in guards), f"{path.name}: __main__ không ở cuối"
