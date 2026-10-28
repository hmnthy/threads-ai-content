"""Tự làm mới token Threads long-lived ở đầu job snapshot (bài học 2026-10-27: token hết hạn, job
snapshot lỗi ~26h — khoảng snapshot đó không hồi cứu được; cảnh báo < 7 ngày chưa từng bật vì
chưa ai làm mới token qua code).

Mỗi lần job snapshot chạy: nếu lần đổi gần nhất đã quá `REFRESH_EVERY` (hoặc chưa từng đổi qua
code) → đổi token (Meta: token ≥ 24h tuổi và còn hạn) → GHI ĐÈ dòng `THREADS_ACCESS_TOKEN` trong
`.env` của chính checkout (Thy chọn phương án A 2026-10-28: 1 chỗ chứa token duy nhất) → cập nhật
`os.environ` cho lần chạy này → ghi mốc + hạn vào `data/cache/.token_meta.json` (không chứa token).
Ghi `.env` TRƯỚC, ghi mốc SAU: tài liệu Meta không nói token cũ còn hiệu lực sau khi đổi.

Không bao giờ raise (đổi lỗi thì token cũ vẫn dùng tới khi hết hạn; `job_health` cảnh báo). Chỉ
thư mục chính: worktree (`.git` là file) bỏ qua — đổi token ở worktree có thể vô hiệu token trong
`.env` của thư mục chính (ADR-0019). Không bao giờ in token.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
TOKEN_ENV = "THREADS_ACCESS_TOKEN"

# Quy tắc vận hành, không phải tham số thống kê: token sống 60 ngày; đổi mỗi 7 ngày để luôn còn
# ≥ 53 ngày — đủ dư cho máy tắt nhiều tuần mà vẫn ≪ 60, và ≥ 24h (ngưỡng tối thiểu Meta cho đổi).
REFRESH_EVERY = timedelta(days=7)
# Quy tắc vận hành: Windows từ chối thay `.env` khi process khác đang mở nó (job NLP, hook đầu
# phiên, antivirus) — thử lại vài lần ngắn trước khi coi là lỗi (token mới đã đổi ở Meta rồi).
ENV_WRITE_ATTEMPTS = 3
ENV_WRITE_PAUSE_S = 0.5


def refresh_due(now: datetime) -> bool:
    from src.api.auth import read_token_meta

    meta = read_token_meta()
    return meta is None or now - meta["issued_at"] >= REFRESH_EVERY


def _save_token(token: str) -> None:
    from dotenv import set_key

    for attempt in range(ENV_WRITE_ATTEMPTS):
        try:
            set_key(ENV_FILE, TOKEN_ENV, token, quote_mode="never")
            return
        except OSError:
            if attempt == ENV_WRITE_ATTEMPTS - 1:
                raise
            time.sleep(ENV_WRITE_PAUSE_S)


def refresh_token_if_due(now: datetime | None = None) -> str:
    """Đổi token nếu tới hạn; trả 1 dòng trạng thái (đã in vào log của job). Không raise.
    Mỗi lần lỗi ghi dấu vào file mốc (`record_token_refresh_failure`) cho `job_health`."""
    now = now or datetime.now(UTC)
    stage = "check"
    try:
        if (REPO_ROOT / ".git").is_file():
            return _say(
                "token refresh: skipped (linked worktree — only the main checkout refreshes)"
            )
        if not refresh_due(now):
            return _say("token refresh: not due")
        from dotenv import dotenv_values

        from src.api import auth

        current = (dotenv_values(ENV_FILE).get(TOKEN_ENV) or "").strip()
        if not current:
            return _say(f"token refresh: skipped ({TOKEN_ENV} not set in {ENV_FILE.name})")
        stage = "meta"
        refreshed = asyncio.run(auth.refresh_long_lived_token(current))
        stage = "save"
        # trước khi ghi .env: dù ghi lỗi, ingest của chính lần chạy này vẫn dùng token mới
        os.environ[TOKEN_ENV] = refreshed.access_token
        _save_token(refreshed.access_token)
        stage = "record"
        auth.record_token_refreshed(refreshed.expires_in_seconds, now)
    except Exception as exc:
        # chỉ tên lỗi + thông điệp của Meta — ThreadsAPIError không chứa URL/token
        reason = f"{type(exc).__name__}: {exc}"
        consequence = {
            "check": "old token kept",
            "meta": "old token kept",
            "save": "refreshed at Meta but could NOT save .env — the old token may stop working; "
            "create a new one if the next snapshot fails",
            "record": ".env already has the new token; only the refresh date was not recorded",
        }[stage]
        if stage != "record":
            _record_failure(reason, now)
        return _say(f"token refresh: FAILED at {stage} ({reason}) — {consequence}")
    expires = now + timedelta(seconds=refreshed.expires_in_seconds)
    return _say(f"token refresh: OK (expires {expires.date().isoformat()})")


def _record_failure(reason: str, now: datetime) -> None:
    try:
        from src.api import auth

        auth.record_token_refresh_failure(reason, now)
    except Exception as exc:  # không được che dòng FAILED gốc
        print(f"token refresh: could not record the failure ({type(exc).__name__})", flush=True)


def _say(line: str) -> str:
    print(line, flush=True)
    return line
