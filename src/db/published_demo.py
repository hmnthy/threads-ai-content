"""File demo RAG đã publish — API chỉ phát nguyên file, không truy xuất phía máy chủ (ADR-0037 D3).

Hai chế độ, cùng cổng với bản sao DB (`src/db/published.py`):
- Laptop / test (không có `VERCEL=1`): đọc file dựng sẵn ở `LOCAL_FILES` (gitignored).
- Vercel (`VERCEL=1`): tải từ Blob riêng tư, pathname cố định dưới `BLOB_PREFIX`, giữ trong bộ nhớ
  của instance; cứ `REVALIDATE_S` hỏi lại bằng ETag (304 = không đổi). Tải lỗi khi đã có bản cũ →
  giữ bản cũ; chưa có bản nào → `DemoFileUnavailableError` (API trả 503).

**Chỉ phát tên trong danh sách cố định** (`DEMO_FILE_NAMES`): tên người gọi gửi lên không bao giờ
được ghép vào pathname — Blob này giữ cả bản sao DB (ADR-0025). Module này không import
`src/rag_demo/` (gói API trên Vercel không kéo thư viện của bước dựng — ADR-0037 Hệ quả).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from src.db.published import (
    DOWNLOAD_TIMEOUT_S,
    RETRY_WITHOUT_COPY_S,
    STORE_ID_ENV,
    blob_credential,
    blob_url,
)

logger = logging.getLogger(__name__)

# Chưa chia file (ADR-0037 D3: 1,37 MB < 4 MB) → chỉ có `common`; khi chia mới thêm q01…q10.
DEMO_FILE_NAMES: tuple[str, ...] = ("common",)
BLOB_PREFIX = "rag-demo/"
# Đường dẫn tương đối như `DEFAULT_DB_PATH` (chạy từ root repo); khớp `src/rag_demo/demo_file.py`
# `DEMO_PATH` (test kiểm — không import để gói API không kéo bước dựng).
LOCAL_FILES: dict[str, Path] = {"common": Path("data/rag_demo/demo.json")}
# Quy tắc vận hành, không phải tham số thống kê: file chỉ đổi khi Thy dựng lại + publish tay →
# hỏi lại Blob mỗi 15 phút là đủ (mỗi lần không đổi chỉ là 1 phản hồi 304).
REVALIDATE_S = 900
# Quy tắc vận hành: trình duyệt giữ 5 phút rồi hỏi lại bằng ETag (304 = không tải lại ~1,4 MB).
BROWSER_MAX_AGE_S = 300
# `private`: CDN của Vercel và mọi proxy dùng chung KHÔNG được giữ response. Header CORS chỉ có khi
# request mang `Origin` được phép, nên một bản CDN giữ từ request không có `Origin` (mở thẳng link,
# bot, curl) sẽ làm trang demo lỗi CORS với mọi người cho tới khi hết hạn. Đổi lại mỗi lượt xem mới
# là một lượt Function (ADR-0037 "Rủi ro chấp nhận": theo dõi Usage).
CACHE_CONTROL = f"private, max-age={BROWSER_MAX_AGE_S}"


class DemoFileUnavailableError(RuntimeError):
    """Chưa có file nào dùng được (chưa dựng / chưa publish / tải lỗi lần đầu / thiếu cấu hình)."""


class DemoFileRemovedError(DemoFileUnavailableError):
    """Blob trả 404: file đã bị gỡ có chủ ý (VD bài vừa bị xoá trên Threads) → bỏ cả bản trong bộ
    nhớ, không phát tiếp như một lỗi tạm."""


def blob_pathname(name: str) -> str:
    """Pathname trên Blob của một tên trong danh sách; tên khác → `KeyError` (không bao giờ ghép
    chuỗi tuỳ ý). Dùng chung cho bước publish (`scripts/rag_demo_build.py`) và API."""
    if name not in DEMO_FILE_NAMES:
        raise KeyError(name)
    return f"{BLOB_PREFIX}{name}.json"


def check_demo_bytes(data: bytes) -> None:
    """Chặn phát trang lỗi HTML hay file cắt cụt: phải là object JSON có `format` kiểu số nguyên."""
    try:
        parsed = json.loads(data)
    except ValueError as exc:
        raise DemoFileUnavailableError("demo file is not valid JSON") from exc
    if not isinstance(parsed, dict) or type(parsed.get("format")) is not int:
        raise DemoFileUnavailableError("demo file has no integer 'format'")


def etag_of(body: bytes) -> str:
    """ETag mạnh = sha256 của nội dung: cùng byte thì cùng ETag trên mọi instance."""
    return f'"{hashlib.sha256(body).hexdigest()}"'


def read_local(name: str) -> bytes:
    path = LOCAL_FILES[name]
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise DemoFileUnavailableError(f"{path} is not built yet") from exc


@dataclass
class _Copy:
    body: bytes
    etag: str | None


@dataclass
class PublishedDemo:
    store_id: str
    clock: Callable[[], float] = time.monotonic
    transport: httpx.BaseTransport | None = None  # test bơm transport giả
    _copies: dict[str, _Copy] = field(default_factory=dict, init=False)
    _checked_at: dict[str, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @classmethod
    def from_env(cls) -> PublishedDemo | None:
        """Chỉ bật trên Vercel (`VERCEL=1`), cùng lý do với `PublishedDb.from_env`: `.env` laptop
        được nạp lúc import nên không dựa vào biến Blob để bật."""
        if os.environ.get("VERCEL") != "1":
            return None
        return cls(store_id=os.environ.get(STORE_ID_ENV, "").strip())

    def get(self, name: str, oidc_token: str | None) -> bytes:
        """Nội dung file `name` (đã ở danh sách). Một khoá chung: file nhỏ, tải nhanh; luồng khác
        chờ tối đa `DOWNLOAD_TIMEOUT_S` (có bản cũ thì không chờ)."""
        pathname = blob_pathname(name)
        if not self._lock.acquire(blocking=False):
            copy = self._copies.get(name)
            if copy is not None:
                return copy.body
            if not self._lock.acquire(timeout=DOWNLOAD_TIMEOUT_S):
                raise DemoFileUnavailableError("timed out waiting for the first load")
        try:
            return self._get_locked(name, pathname, oidc_token)
        finally:
            self._lock.release()

    def _get_locked(self, name: str, pathname: str, oidc_token: str | None) -> bytes:
        now = self.clock()
        copy = self._copies.get(name)
        checked = self._checked_at.get(name)
        if checked is not None:
            wait = REVALIDATE_S if copy is not None else RETRY_WITHOUT_COPY_S
            if now - checked < wait:
                if copy is not None:
                    return copy.body
                raise DemoFileUnavailableError("previous load failed; waiting before a retry")
        # ghi mốc TRƯỚC khi tải: cả khi lỗi, lần thử kế tiếp chờ tới hạn, không dội Blob
        self._checked_at[name] = now
        try:
            fresh = self._download(pathname, copy, oidc_token)
        # bắt rộng có chủ ý (như `PublishedDb`): lỗi lọt ra thành 500 không có header CORS
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, DemoFileRemovedError):
                self._copies.pop(name, None)
                logger.warning("RAG demo file removed from Blob, no longer served: %s", reason)
                raise
            if copy is None:
                logger.error("RAG demo file unavailable: %s", reason)
                raise DemoFileUnavailableError(f"cannot load the demo file: {reason}") from exc
            logger.warning("RAG demo refresh failed, serving the previous copy: %s", reason)
            return copy.body
        if fresh is not None:
            self._copies[name] = fresh
            copy = fresh
        assert copy is not None  # 304 chỉ trả khi đã có bản (kiểm trong `_download`)
        return copy.body

    def _download(self, pathname: str, copy: _Copy | None, oidc_token: str | None) -> _Copy | None:
        """Bản mới, hoặc None khi Blob trả 304 cho đúng ETag của bản đang có."""
        if not self.store_id:
            raise DemoFileUnavailableError(f"{STORE_ID_ENV} is not set")
        token, source = blob_credential(oidc_token)
        headers = {"Authorization": f"Bearer {token}"}
        if copy is not None and copy.etag is not None:
            headers["If-None-Match"] = copy.etag
        with httpx.Client(timeout=DOWNLOAD_TIMEOUT_S, transport=self.transport) as client:
            resp = client.get(blob_url(self.store_id, pathname), headers=headers)
        if resp.status_code == 304:
            # 304 chỉ hợp lệ khi đã hỏi bằng ETag của bản đang có — không thay cho lần tải đầu
            if "If-None-Match" not in headers:
                raise DemoFileUnavailableError("HTTP 304 without a conditional request")
            return None
        if resp.status_code == 404:
            raise DemoFileRemovedError(f"Blob returned HTTP 404 for {pathname}")
        if resp.is_error:
            raise DemoFileUnavailableError(
                f"Blob returned HTTP {resp.status_code} (credential from {source})"
            )
        check_demo_bytes(resp.content)
        logger.info(
            "RAG demo file loaded (%d bytes, credential from %s)", len(resp.content), source
        )
        return _Copy(body=resp.content, etag=resp.headers.get("etag"))
