from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
from dotenv import load_dotenv

load_dotenv()

THREADS_REFRESH_URL: Final = "https://graph.threads.net/refresh_access_token"
LONG_LIVED_TOKEN_LIFETIME: Final = timedelta(days=60)
EXPIRY_WARNING_THRESHOLD: Final = timedelta(days=7)
TOKEN_META_PATH: Final = Path("data/cache/.token_meta.json")

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
    """Exchange a still-valid long-lived token for a fresh 60-day one."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            THREADS_REFRESH_URL,
            params={"grant_type": "th_refresh_token", "access_token": current_token},
        )
        response.raise_for_status()
        payload = response.json()
    _record_token_issued_now()
    return RefreshedToken(
        access_token=payload["access_token"],
        expires_in_seconds=payload["expires_in"],
    )


def _record_token_issued_now() -> None:
    TOKEN_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_META_PATH.write_text(
        json.dumps({"issued_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


def days_until_expiry() -> int | None:
    """Days remaining before the long-lived token likely expires, or None if unknown.

    Unknown until the token has been refreshed at least once through this module,
    since Threads does not expose a "time remaining" lookup for an arbitrary token.
    """
    if not TOKEN_META_PATH.exists():
        return None
    meta = json.loads(TOKEN_META_PATH.read_text(encoding="utf-8"))
    issued_at = datetime.fromisoformat(meta["issued_at"])
    expires_at = issued_at + LONG_LIVED_TOKEN_LIFETIME
    remaining = expires_at - datetime.now(UTC)
    return max(remaining.days, 0)


def should_warn_expiry() -> bool:
    remaining = days_until_expiry()
    return remaining is not None and remaining <= EXPIRY_WARNING_THRESHOLD.days
