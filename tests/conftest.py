"""Cấu hình pytest dùng chung.

Khi pytest chạy bên trong git hook (pre-commit lúc `git commit -a` / pathspec), git xuất
`GIT_INDEX_FILE` (đường dẫn TUYỆT ĐỐI tới index tạm của repo thật), `GIT_DIR`… Test nào chạy
`git` trong repo tạm sẽ thừa hưởng chúng và ghi vào index của repo THẬT (đã xảy ra
2026-10-01, code-reviewer tái hiện). Xoá mọi biến `GIT_*` cho từng test — giống
`git.no_git_env` của pre-commit — trừ biến cấu hình/đường dẫn chương trình vô hại.

Không bao giờ tải dữ liệu thật lên Vercel Blob (ADR-0025): test nào chạy 1 cron job đều đi qua
bước publish (`src/pipeline/publish.py`), và `src/api/auth.py` nạp `.env` thật lúc import — có
thể mang `DB_BLOB_PATH` + `BLOB_READ_WRITE_TOKEN` vào `os.environ` của cả phiên test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import src.pipeline.publish as publish_module

_KEEP = ("GIT_CONFIG_", "GIT_EXEC_PATH", "GIT_SSH", "GIT_ASKPASS", "GIT_TERMINAL_PROMPT")
_BLOB_ENV = (
    "DB_BLOB_PATH",
    "BLOB_READ_WRITE_TOKEN",
    "VERCEL_BLOB_READ_WRITE_TOKEN",
    "BLOB_STORE_ID",
    "VERCEL",
    "VERCEL_OIDC_TOKEN",
    "VERCEL_OIDC_TOKEN_FILE",
)


@pytest.fixture(autouse=True)
def _isolate_from_git_hook_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("GIT_") and not name.startswith(_KEEP):
            monkeypatch.delenv(name)


def _refuse_real_upload(pathname: str, body: bytes, token: str) -> None:
    raise AssertionError(f"a test tried to upload {len(body)} bytes to Vercel Blob ({pathname})")


@pytest.fixture(autouse=True)
def _never_publish_for_real(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in _BLOB_ENV:
        monkeypatch.delenv(name, raising=False)
    # thư mục giả không có .git → test publish chạy được cả khi repo là worktree (ADR-0019)
    monkeypatch.setattr(publish_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(publish_module, "ENV_FILE", tmp_path / "no-such.env")
    monkeypatch.setattr(publish_module, "vercel_upload", _refuse_real_upload)
    monkeypatch.setattr(publish_module, "STATE_PATH", tmp_path / "publish_state.json")
