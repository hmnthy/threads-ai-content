"""Cấu hình pytest dùng chung.

Khi pytest chạy bên trong git hook (pre-commit lúc `git commit -a` / pathspec), git xuất
`GIT_INDEX_FILE` (đường dẫn TUYỆT ĐỐI tới index tạm của repo thật), `GIT_DIR`… Test nào chạy
`git` trong repo tạm sẽ thừa hưởng chúng và ghi vào index của repo THẬT (đã xảy ra
2026-10-01, code-reviewer tái hiện). Xoá mọi biến `GIT_*` cho từng test — giống
`git.no_git_env` của pre-commit — trừ biến cấu hình/đường dẫn chương trình vô hại.
"""

from __future__ import annotations

import os

import pytest

_KEEP = ("GIT_CONFIG_", "GIT_EXEC_PATH", "GIT_SSH", "GIT_ASKPASS", "GIT_TERMINAL_PROMPT")


@pytest.fixture(autouse=True)
def _isolate_from_git_hook_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("GIT_") and not name.startswith(_KEEP):
            monkeypatch.delenv(name)
