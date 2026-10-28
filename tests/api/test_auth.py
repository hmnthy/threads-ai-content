import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import respx
from httpx import Response
from pytest import MonkeyPatch

from src.api import auth
from src.api.auth import MissingCredentialsError, load_credentials
from src.api.auth import refresh_long_lived_token as _real_refresh
from src.api.client import ThreadsAPIError

# lấy lúc import file test, trước khi conftest thay `auth.refresh_long_lived_token` bằng bản từ chối
refresh_long_lived_token = _real_refresh


def test_load_credentials_returns_values_from_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("THREADS_APP_ID", "app-1")
    monkeypatch.setenv("THREADS_APP_SECRET", "secret-1")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "token-1")
    monkeypatch.setenv("THREADS_USER_ID", "user-1")

    creds = load_credentials()

    assert creds.app_id == "app-1"
    assert creds.access_token == "token-1"


def test_load_credentials_raises_on_missing_values(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("THREADS_APP_ID", raising=False)
    monkeypatch.delenv("THREADS_APP_SECRET", raising=False)
    monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("THREADS_USER_ID", raising=False)

    with pytest.raises(MissingCredentialsError, match="THREADS_APP_ID"):
        load_credentials()


@respx.mock
async def test_refresh_long_lived_token_returns_new_token_without_side_effects(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(auth, "TOKEN_META_PATH", tmp_path / "token_meta.json")
    route = respx.get(auth.THREADS_REFRESH_URL).mock(
        return_value=Response(200, json={"access_token": "new-token", "expires_in": 5184000})
    )

    refreshed = await refresh_long_lived_token("old-token")

    assert refreshed.access_token == "new-token"
    assert refreshed.expires_in_seconds == 5184000
    assert route.calls.last.request.url.params["grant_type"] == "th_refresh_token"
    # người gọi lưu token mới trước rồi mới ghi mốc (token_refresh.py)
    assert not (tmp_path / "token_meta.json").exists()


@respx.mock
async def test_refresh_error_never_carries_the_token() -> None:
    # HTTPStatusError của raise_for_status() chứa URL đầy đủ — token nằm trong query string
    respx.get(auth.THREADS_REFRESH_URL).mock(
        return_value=Response(400, json={"error": {"message": "Session has expired", "code": 190}})
    )

    with pytest.raises(ThreadsAPIError) as info:
        await refresh_long_lived_token("secret-token-XYZ")

    assert info.value.status_code == 400 and info.value.error_code == 190
    assert "secret-token-XYZ" not in str(info.value)


def test_record_and_read_token_meta(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(auth, "TOKEN_META_PATH", tmp_path / "token_meta.json")
    issued = datetime(2026, 11, 1, tzinfo=UTC)

    auth.record_token_refreshed(5184000, issued)

    assert auth.read_token_meta() == {
        "issued_at": issued,
        "expires_at": issued + timedelta(seconds=5184000),
    }
    (tmp_path / "token_meta.json").write_text("{broken", encoding="utf-8")
    assert auth.read_token_meta() is None


def test_days_until_expiry_returns_none_without_metadata(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(auth, "TOKEN_META_PATH", tmp_path / "missing.json")
    assert auth.days_until_expiry() is None


def test_should_warn_expiry_true_when_within_threshold(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    meta_path = tmp_path / "token_meta.json"
    monkeypatch.setattr(auth, "TOKEN_META_PATH", meta_path)
    issued_at = datetime.now(UTC) - timedelta(days=55)  # 5 days left of the 60-day lifetime
    meta_path.write_text(json.dumps({"issued_at": issued_at.isoformat()}), encoding="utf-8")

    assert auth.should_warn_expiry() is True


def test_should_warn_expiry_false_when_far_from_expiry(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    meta_path = tmp_path / "token_meta.json"
    monkeypatch.setattr(auth, "TOKEN_META_PATH", meta_path)
    issued_at = datetime.now(UTC) - timedelta(days=1)
    meta_path.write_text(json.dumps({"issued_at": issued_at.isoformat()}), encoding="utf-8")

    assert auth.should_warn_expiry() is False
