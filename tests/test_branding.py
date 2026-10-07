"""Thương hiệu: câu miễn trừ Meta phải có ở mọi nơi công khai tên sản phẩm (ADR-0009); logo Unknot
dùng đúng file gốc, không sửa tay (ADR-0021).

Sổ luật chỉ có kiểu `forbid` (cấm) — kiểm "phải có" nằm ở đây để việc xoá câu miễn trừ bị chặn
ở pre-commit (test nhanh).
"""

from __future__ import annotations

import hashlib
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


DASHBOARD = REPO_ROOT / "src" / "dashboard"


def test_favicon_is_the_unknot_mark_byte_for_byte() -> None:
    # ADR-0021: app/icon.svg là bản sao duy nhất được phép của file brand; không sửa tay
    mark = (DASHBOARD / "public" / "brand" / "unthreaded-mark.svg").read_bytes()
    assert (DASHBOARD / "src" / "app" / "icon.svg").read_bytes() == mark
    assert not (DASHBOARD / "src" / "app" / "favicon.ico").exists()


@pytest.mark.parametrize("component", ["Nav.tsx", "LandingNav.tsx"])
def test_navbars_render_the_brand_logo(component: str) -> None:
    text = (DASHBOARD / "src" / "components" / component).read_text(encoding="utf-8")
    assert '<BrandLogo variant="lockup"' in text


# ADR-0021: file logo không sửa tay — đổi thương hiệu thì quay lại vòng thiết kế, sinh lại file và
# cập nhật dấu ở đây cùng commit. Repo ép xuống dòng LF cho mọi file text (thuộc tính `eol=lf`) nên
# dấu giống nhau trên Windows lẫn máy CI.
# Khoá = tên file bỏ tiền tố "unthreaded-" và đuôi ".svg"
BRAND_SHA256 = {
    "lockup-animated-once": "0a598ba38a3bde12e866e47da70a48eb72cb070a047b4fbb9b442ad027b8b318",
    "lockup-animated": "804f6b342c258d061ee3e74ed0c8c3d0485981da2fc30ffdbe6be57378690118",
    "lockup-tagline": "9e92a73f17e61e4fb4153aee058b6f51e88a3937c1f1cfeb4139506f24c05c4e",
    "lockup": "324875f5a4a08b0732a0cf172549113e6d1130a73c808e6c7630092dde4f34fb",
    "mark": "5dce99e14c17a31e0eddf2dfc9ac7ea13713d2bb193231de97e600f21a15cc00",
}


def test_brand_assets_are_not_hand_edited() -> None:
    brand = DASHBOARD / "public" / "brand"
    files = {f"unthreaded-{key}.svg": digest for key, digest in BRAND_SHA256.items()}
    assert {p.name for p in brand.glob("*.svg")} == set(files)  # bỏ qua file rác của hệ điều hành
    for name, digest in files.items():
        assert hashlib.sha256((brand / name).read_bytes()).hexdigest() == digest, name
