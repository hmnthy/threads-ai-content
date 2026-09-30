"""Câu miễn trừ Meta phải có ở mọi nơi công khai tên sản phẩm (ADR-0009).

Sổ luật chỉ có kiểu `forbid` (cấm) — kiểm "phải có" nằm ở đây để việc xoá câu miễn trừ bị chặn
ở pre-commit (test nhanh).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

DISCLAIMERS = {
    "README.md": "Not affiliated with Meta. Threads is a trademark of Meta Platforms, Inc.",
    "README.vi.md": "Không liên kết với Meta. Threads là nhãn hiệu của Meta Platforms, Inc.",
    "README.fr.md": "Sans lien avec Meta. Threads est une marque de Meta Platforms, Inc.",
    "src/dashboard/src/app/page.tsx": (
        "Not affiliated with Meta. Threads is a trademark of Meta Platforms, Inc."
    ),
}


@pytest.mark.parametrize(("path", "sentence"), DISCLAIMERS.items())
def test_meta_disclaimer_present(path: str, sentence: str) -> None:
    # Gộp khoảng trắng: câu có thể bị ngắt dòng (README wrap 100 cột, JSX wrap)
    text = " ".join((REPO_ROOT / path).read_text(encoding="utf-8").split())
    assert sentence in text
