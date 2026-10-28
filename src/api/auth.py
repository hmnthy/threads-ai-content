from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
from dotenv import load_dotenv

from src.api.client import ThreadsAPIError

load_dotenv()

THREADS_REFRESH_URL: Final = "https://graph.threads.net/refresh_access_token"
LONG_LIVED_TOKEN_LIFETIME: Final = timedelta(days=60)
EXPIRY_WARNING_THRESHOLD: Final = timedelta(days=7)
# Neo vào thư mục repo (không theo thư mục đang đứng): job_health đọc cùng file theo đường dẫn repo
TOKEN_META_PATH: Final = Path(__file__).resolve().parents[2] / "data" / "cache" / ".token_meta.json"

REQUIRED_ENV_VARS: Final = (
    "THREADS_APP_ID",
    "THREADS_APP_SECRET",
    "THREADS_ACCESS_TOKEN",
    "THREADS_USER_ID",
)


class MissingCredentialsError(RuntimeError):
    """Raised when one or more required Threads credentials are missing from .env."""


@dataclass(frozen=True)
class ThreadsCredentials:
    app_id: str
    app_secret: str
    access_token: str
    user_id: str


def load_credentials() -> ThreadsCredentials:
    raw = {name: os.getenv(name) for name in REQUIRED_ENV_VARS}
    missing = [name for name, value in raw.items() if not value]
    if missing:
        raise MissingCredentialsError(f"Missing required .env values: {', '.join(missing)}")
    values: dict[str, str] = {name: value for name, value in raw.items() if value}
    return ThreadsCredentials(
        app_id=values["THREADS_APP_ID"],
        app_secret=values["THREADS_APP_SECRET"],
        access_token=values["THREADS_ACCESS_TOKEN"],
        user_id=values["THREADS_USER_ID"],
    )


@dataclass(frozen=True)
class RefreshedToken:
    access_token: str
    expires_in_seconds: int


async def refresh_long_lived_token(current_token: str) -> RefreshedToken:
    """Exchange a still-valid long-lived token for a fresh 60-day one (Meta: token ≥ 24h tuổi và
    còn hạn — developers.facebook.com/docs/threads/get-started/long-lived-tokens). Không ghi gì:
    người gọi lưu token mới TRƯỚC rồi mới `record_token_refreshed` (tài liệu không nói token cũ
    còn hiệu lực sau khi đổi).

    Lỗi → `ThreadsAPIError` dựng từ body, KHÔNG `raise_for_status()`: thông báo của
    `HTTPStatusError` chứa URL đầy đủ, mà token nằm trong query string → lọt vào log của job."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            THREADS_REFRESH_URL,
            params={"grant_type": "th_refresh_token", "access_token": current_token},
        )
    if response.is_error:
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        raise ThreadsAPIError(
            error.get("message", "token refresh failed"),
            status_code=response.status_code,
            error_code=error.get("code"),
            fbtrace_id=error.get("fbtrace_id"),
        )
    payload = response.json()
    expires_in = payload.get("expires_in")
    return RefreshedToken(
        access_token=payload["access_token"],
        # thiếu expires_in → coi là 60 ngày (thời hạn chuẩn), không vứt token mới đã đổi xong
        expires_in_seconds=(
            int(expires_in)
            if expires_in is not None
            else int(LONG_LIVED_TOKEN_LIFETIME.total_seconds())
        ),
    )


def _write_token_meta(meta: dict[str, str]) -> None:
    TOKEN_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_META_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta), encoding="utf-8")
    os.replace(tmp, TOKEN_META_PATH)


def record_token_refreshed(expires_in_seconds: int, now: datetime | None = None) -> None:
    """Ghi mốc đổi token + hạn chính xác Meta trả về (không giữ token), xoá dấu lỗi cũ."""
    issued = now or datetime.now(UTC)
    _write_token_meta(
        {
            "issued_at": issued.isoformat(),
            "expires_at": (issued + timedelta(seconds=expires_in_seconds)).isoformat(),
        }
    )


def record_token_refresh_failure(error: str, now: datetime | None = None) -> None:
    """Ghi dấu lần đổi lỗi (giữ mốc đổi thành công cũ nếu có) — `job_health` cần tín hiệu cả khi
    CHƯA từng đổi thành công (bài học 2026-10-27: không có file mốc = không có cảnh báo).
    `error` chỉ là tên lỗi + mã Meta, không bao giờ chứa token."""
    at = (now or datetime.now(UTC)).isoformat()
    try:
        meta = json.loads(TOKEN_META_PATH.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            meta = {}
    except (OSError, ValueError):
        meta = {}
    meta.setdefault("first_failed_at", at)
    meta["last_failed_at"] = at
    meta["last_error"] = error
    _write_token_meta(meta)


def read_token_meta() -> dict[str, datetime] | None:
    """`issued_at` + `expires_at` của lần đổi token gần nhất qua code; None nếu chưa có / hỏng.
    File cũ chỉ có `issued_at` → hạn = issued_at + 60 ngày."""
    try:
        raw = json.loads(TOKEN_META_PATH.read_text(encoding="utf-8"))
        issued_at = datetime.fromisoformat(raw["issued_at"])
        expires_raw = raw.get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_raw)
            if expires_raw
            else issued_at + LONG_LIVED_TOKEN_LIFETIME
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return {"issued_at": issued_at, "expires_at": expires_at}


def days_until_expiry() -> int | None:
    """Days remaining before the long-lived token expires, or None if unknown.

    Unknown until the token has been refreshed at least once through code (the snapshot job does
    it automatically — `src/pipeline/token_refresh.py`), since Threads does not expose a
    "time remaining" lookup for an arbitrary token.
    """
    meta = read_token_meta()
    if meta is None:
        return None
    remaining = meta["expires_at"] - datetime.now(UTC)
    return max(remaining.days, 0)


def should_warn_expiry() -> bool:
    remaining = days_until_expiry()
    return remaining is not None and remaining <= EXPIRY_WARNING_THRESHOLD.days
