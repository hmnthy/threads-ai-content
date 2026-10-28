"""Tự làm mới token Threads ở đầu job snapshot (phương án A: ghi đè `.env`). Không gọi Meta: hàm
đổi token được thay bằng bản giả; `tests/conftest.py` chặn bản thật ở mọi test."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import src.api.auth as auth_module
import src.pipeline.token_refresh as token_refresh_module
from src.api.auth import RefreshedToken, read_token_meta, record_token_refreshed
from src.api.auth import refresh_long_lived_token as _real_refresh  # trước khi conftest thay
from src.api.client import ThreadsAPIError
from src.pipeline.token_refresh import REFRESH_EVERY, refresh_due, refresh_token_if_due

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
OLD = "old-token-AAAA"
NEW = "new-token-BBBB"
SIXTY_DAYS = 60 * 86400


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".env"
    path.write_text(
        f"THREADS_APP_ID=app\nTHREADS_ACCESS_TOKEN={OLD}\nDB_BLOB_PATH=threads.db\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(token_refresh_module, "ENV_FILE", path)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", OLD)
    return path


@pytest.fixture
def fake_refresh(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def refresh(current_token: str) -> RefreshedToken:
        calls.append(current_token)
        return RefreshedToken(access_token=NEW, expires_in_seconds=SIXTY_DAYS)

    monkeypatch.setattr(auth_module, "refresh_long_lived_token", refresh)
    return calls


def test_due_without_meta_then_every_seven_days() -> None:
    assert refresh_due(NOW)  # chưa từng đổi qua code
    record_token_refreshed(SIXTY_DAYS, NOW - REFRESH_EVERY + timedelta(hours=1))
    assert not refresh_due(NOW)
    record_token_refreshed(SIXTY_DAYS, NOW - REFRESH_EVERY)
    assert refresh_due(NOW)


def test_refresh_rewrites_only_the_token_line_and_records_expiry(
    env_file: Path, fake_refresh: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    line = refresh_token_if_due(NOW)

    assert fake_refresh == [OLD]
    assert env_file.read_text(encoding="utf-8") == (
        f"THREADS_APP_ID=app\nTHREADS_ACCESS_TOKEN={NEW}\nDB_BLOB_PATH=threads.db\n"
    )
    assert os.environ["THREADS_ACCESS_TOKEN"] == NEW  # ingest của chính lần chạy này dùng ngay
    meta = read_token_meta()
    assert meta is not None
    assert meta["issued_at"] == NOW and meta["expires_at"] == NOW + timedelta(days=60)
    assert line == "token refresh: OK (expires 2027-01-04)"
    out = capsys.readouterr().out
    assert NEW not in out and OLD not in out  # không bao giờ in token
    assert NEW not in auth_module.TOKEN_META_PATH.read_text(encoding="utf-8")


def test_not_due_does_not_call_meta(env_file: Path, fake_refresh: list[str]) -> None:
    record_token_refreshed(SIXTY_DAYS, NOW - timedelta(days=1))

    assert refresh_token_if_due(NOW) == "token refresh: not due"
    assert fake_refresh == []


def test_meta_error_keeps_old_token_and_never_prints_it(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(current_token: str) -> RefreshedToken:
        raise ThreadsAPIError("Session has expired", status_code=400, error_code=190)

    monkeypatch.setattr(auth_module, "refresh_long_lived_token", failing)

    line = refresh_token_if_due(NOW)
    later = refresh_token_if_due(NOW + timedelta(hours=4))

    assert line.startswith("token refresh: FAILED at meta (ThreadsAPIError")
    assert line.endswith("old token kept")
    assert OLD not in line
    assert f"THREADS_ACCESS_TOKEN={OLD}" in env_file.read_text(encoding="utf-8")
    assert read_token_meta() is None  # vẫn tới hạn → lần chạy sau thử lại
    assert later.startswith("token refresh: FAILED at meta")
    # dấu lỗi cho job_health, kể cả khi CHƯA từng đổi thành công (bài học 2026-10-27)
    raw = json.loads(auth_module.TOKEN_META_PATH.read_text(encoding="utf-8"))
    assert raw["first_failed_at"] == NOW.isoformat()
    assert raw["last_failed_at"] == (NOW + timedelta(hours=4)).isoformat()
    assert raw["last_error"].startswith("ThreadsAPIError")
    assert OLD not in json.dumps(raw)


def test_env_write_retries_then_reports_the_lost_token(
    env_file: Path, fake_refresh: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # ghi .env TRƯỚC, mốc SAU: không ghi được token mới thì không được đánh dấu "đã đổi", và log
    # phải nói rõ Meta ĐÃ đổi (token cũ có thể ngừng chạy) — không phải "old token kept"
    import dotenv

    attempts: list[int] = []

    def broken_set_key(*args: object, **kwargs: object) -> None:
        attempts.append(1)
        raise PermissionError(".env is locked")

    monkeypatch.setattr(dotenv, "set_key", broken_set_key)
    monkeypatch.setattr(token_refresh_module, "ENV_WRITE_PAUSE_S", 0)

    line = refresh_token_if_due(NOW)

    assert len(attempts) == token_refresh_module.ENV_WRITE_ATTEMPTS
    assert line.startswith("token refresh: FAILED at save (PermissionError")
    assert "refreshed at Meta but could NOT save .env" in line
    assert read_token_meta() is None


def test_env_write_succeeds_on_retry(
    env_file: Path, fake_refresh: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import dotenv

    real_set_key = dotenv.set_key
    calls: list[int] = []

    def flaky_set_key(*args: object, **kwargs: object) -> object:
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError(".env is open in another process")
        return real_set_key(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(dotenv, "set_key", flaky_set_key)
    monkeypatch.setattr(token_refresh_module, "ENV_WRITE_PAUSE_S", 0)

    assert refresh_token_if_due(NOW).startswith("token refresh: OK")
    assert f"THREADS_ACCESS_TOKEN={NEW}" in env_file.read_text(encoding="utf-8")


def test_missing_expires_in_defaults_to_sixty_days(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import respx
    from httpx import Response

    # bản thật (conftest đã thay auth.refresh_long_lived_token) — lấy lại từ module con trỏ cũ
    monkeypatch.setattr(auth_module, "refresh_long_lived_token", _real_refresh)
    with respx.mock:
        respx.get(auth_module.THREADS_REFRESH_URL).mock(
            return_value=Response(200, json={"access_token": NEW})
        )
        line = refresh_token_if_due(NOW)

    assert line == "token refresh: OK (expires 2027-01-04)"


def test_skips_in_a_linked_worktree(
    env_file: Path, fake_refresh: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (token_refresh_module.REPO_ROOT / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")

    assert "linked worktree" in refresh_token_if_due(NOW)
    assert fake_refresh == []


def test_skips_when_env_has_no_token(fake_refresh: list[str]) -> None:
    # conftest trỏ ENV_FILE tới file không tồn tại
    assert "not set" in refresh_token_if_due(NOW)
    assert fake_refresh == []


def test_success_after_failures_clears_the_failure_marker() -> None:
    from scripts import job_health

    auth_module.record_token_refresh_failure("ThreadsAPIError: boom", NOW - timedelta(days=3))
    record_token_refreshed(SIXTY_DAYS, NOW)

    raw = json.loads(auth_module.TOKEN_META_PATH.read_text(encoding="utf-8"))
    assert "first_failed_at" not in raw and "last_error" not in raw
    assert job_health.token_status(auth_module.TOKEN_META_PATH, NOW).startswith("Threads token OK")


def test_failure_after_success_keeps_the_success_fields() -> None:
    record_token_refreshed(SIXTY_DAYS, NOW - timedelta(days=8))
    before = read_token_meta()

    auth_module.record_token_refresh_failure("ThreadsAPIError: boom", NOW)

    assert read_token_meta() == before  # hạn + mốc đổi cũ vẫn còn cho job_health
    raw = json.loads(auth_module.TOKEN_META_PATH.read_text(encoding="utf-8"))
    assert raw["first_failed_at"] == NOW.isoformat()


def test_unsaved_token_is_still_used_by_this_run(
    env_file: Path, fake_refresh: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import dotenv

    def broken_set_key(*args: object, **kwargs: object) -> None:
        raise PermissionError(".env is locked")

    monkeypatch.setattr(dotenv, "set_key", broken_set_key)
    monkeypatch.setattr(token_refresh_module, "ENV_WRITE_PAUSE_S", 0)

    refresh_token_if_due(NOW)

    assert os.environ["THREADS_ACCESS_TOKEN"] == NEW  # ingest lần này vẫn chạy được
