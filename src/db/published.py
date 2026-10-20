"""Bản sao DB đã publish — chế độ chỉ đọc của API trên Vercel (ADR-0025, Hệ quả bước 2).

Bật khi chạy trên Vercel (`VERCEL=1`) và có `DB_BLOB_PATH` (pathname của bản sao trong Vercel Blob
riêng tư); thiếu 1 trong 2 → API đọc `data/threads.db` như cũ. Bản sao được tải về thư mục tạm
(`/tmp` — chỗ ghi được duy nhất của Vercel Function) ở request đầu tiên, rồi mở `mode=ro`
(`connect_readonly`).

Xác thực: Blob riêng tư không có URL công khai. Trên Vercel, token OIDC ngắn hạn chỉ có trong header
`x-vercel-oidc-token` của mỗi request (tài liệu Vercel "System environment variables"), nên lần tải
xảy ra trong request — không ở lúc khởi động. Đọc bằng HTTP GET thường
(`https://<store-id>.private.blob.vercel-storage.com/<pathname>`, header `Authorization: Bearer`,
tài liệu Vercel "Private storage") qua `httpx` có sẵn trong gói API — không thêm SDK.

Đổi mới: instance ấm có thể sống lâu hơn chu kỳ publish → cứ `REVALIDATE_S` lại hỏi Blob bằng ETag
(`If-None-Match`, 304 = không đổi). Tải lỗi khi đã có bản cũ → giữ bản cũ (trang vẫn chạy, số liệu
cũ hơn); chưa có bản nào → `PublishedDbUnavailableError` (API trả 503) và chờ `RETRY_WITHOUT_COPY_S`
mới thử lại.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

BLOB_PATH_ENV = "DB_BLOB_PATH"
# Vercel tự thêm khi nối Blob store vào project (mặc định của SDK `get()` khi dùng OIDC);
# chấp nhận cả dạng `store_<id>` lẫn `<id>`.
STORE_ID_ENV = "BLOB_STORE_ID"
OIDC_HEADER = "x-vercel-oidc-token"

# Quy tắc vận hành, không phải tham số thống kê: publish chạy sau mỗi job (snapshot 4h, NLP
# 1 lần/ngày) nên hỏi lại mỗi 5 phút làm trang công khai trễ tối đa ~5 phút + ≤ 60 giây cache CDN
# của Blob (tài liệu Vercel "Consistent reads"), mỗi lần hỏi khi không đổi chỉ là 1 phản hồi 304.
REVALIDATE_S = 300
# Quy tắc vận hành: chưa có bản sao nào mà lần tải lỗi → trả 503 ngay, chỉ thử lại sau 10 giây —
# không để mỗi request (kể cả bị gọi dồn dập) thành 1 lần gọi Blob; đủ ngắn để 1 lỗi mạng thoáng
# qua lúc cold start không làm trang trống lâu.
RETRY_WITHOUT_COPY_S = 10
DOWNLOAD_TIMEOUT_S = 30.0
# 16 byte đầu của mọi file SQLite 3 (sqlite.org/fileformat.html §1.3) — chặn ghi đè bản sao tốt
# bằng trang lỗi HTML hay file cắt cụt.
SQLITE_HEADER = b"SQLite format 3\x00"
# Byte 18–19 = phiên bản định dạng ghi/đọc: 1 = rollback journal, 2 = WAL (cùng nguồn). Bản sao
# mang cờ WAL mở `mode=ro` sẽ tạo `-wal`/`-shm` cạnh file, và `os.replace` chỉ thay file chính →
# connection mới ghép DB mới với `-shm` cũ. Bước publish phải đặt `journal_mode = DELETE` cho bản
# sao (`conn.backup()` giữ nguyên cờ WAL của DB nguồn — Phase C chuyển WAL).
ROLLBACK_JOURNAL_FLAGS = b"\x01\x01"


class PublishedDbUnavailableError(RuntimeError):
    """Chưa có bản sao nào dùng được (tải lỗi ở lần đầu, thiếu cấu hình/token)."""


def _store_host_id(store_id: str) -> str:
    return store_id.removeprefix("store_").lower()


@dataclass
class PublishedDb:
    blob_path: str
    store_id: str
    local_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "unthreaded")
    clock: Callable[[], float] = time.monotonic
    transport: httpx.BaseTransport | None = None  # test bơm transport giả
    _etag: str | None = field(default=None, init=False)
    _checked_at: float | None = field(default=None, init=False)
    # chỉ True sau khi process này thay file thành công — KHÔNG suy từ `_checked_at` (mốc "đã
    # thử", đặt trước khi tải) hay từ việc file tồn tại (có thể sót từ lần chạy trước)
    _loaded: bool = field(default=False, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @classmethod
    def from_env(cls) -> PublishedDb | None:
        """Chỉ bật trên Vercel (`VERCEL=1` — biến hệ thống Vercel đặt lúc chạy): `.env` của laptop
        được `load_dotenv()` nạp khi import `src.api` và có thể chứa `DB_BLOB_PATH` cho bước
        publish → không có cổng này thì `uvicorn` local và cả bộ test lặng lẽ chuyển sang đọc
        Blob thật. Thử chế độ này ở laptop: đặt thêm `VERCEL=1`."""
        blob_path = os.environ.get(BLOB_PATH_ENV, "").strip()
        if not blob_path or os.environ.get("VERCEL") != "1":
            return None
        return cls(blob_path=blob_path, store_id=os.environ.get(STORE_ID_ENV, "").strip())

    @property
    def local_path(self) -> Path:
        return self.local_dir / "threads.db"

    @property
    def url(self) -> str:
        host = _store_host_id(self.store_id)
        return f"https://{host}.private.blob.vercel-storage.com/{quote(self.blob_path.lstrip('/'))}"

    def _has_copy(self) -> bool:
        # chỉ tính bản do process này tải: file còn sót trong thư mục tạm từ lần chạy trước (laptop)
        # có thể cũ nhiều ngày hoặc của store/pathname khác
        return self._loaded and self.local_path.exists()

    def ensure(self, oidc_token: str | None) -> Path:
        """Trả đường dẫn bản sao cục bộ, tải/hỏi lại Blob khi tới hạn. An toàn khi gọi song song
        (endpoint đồng bộ chạy trong threadpool): chỉ 1 luồng tải; trong lúc đó luồng khác dùng
        bản cũ nếu có, chưa có thì chờ tối đa `DOWNLOAD_TIMEOUT_S` (timeout của httpx tính theo
        từng pha, không phải tổng → không để request dồn lại chiếm hết threadpool vô hạn)."""
        if not self._lock.acquire(blocking=False):
            if self._has_copy():
                return self.local_path
            if not self._lock.acquire(timeout=DOWNLOAD_TIMEOUT_S):
                raise PublishedDbUnavailableError("timed out waiting for the first load")
        try:
            return self._ensure_locked(oidc_token)
        finally:
            self._lock.release()

    def _ensure_locked(self, oidc_token: str | None) -> Path:
        now = self.clock()
        have_copy = self._has_copy()
        if self._checked_at is not None:
            wait = REVALIDATE_S if have_copy else RETRY_WITHOUT_COPY_S
            if now - self._checked_at < wait:
                if have_copy:
                    return self.local_path
                raise PublishedDbUnavailableError("previous load failed; waiting before a retry")
        # ghi mốc TRƯỚC khi tải: cả khi lỗi, lần thử kế tiếp chờ tới hạn, không dội Blob
        self._checked_at = now
        try:
            self._refresh(oidc_token)
        # bắt rộng có chủ ý: lỗi lọt ra middleware thành 500 KHÔNG có header CORS (VD token không
        # phải ASCII → UnicodeEncodeError, BLOB_STORE_ID sai → httpx.InvalidURL)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if not have_copy:
                logger.error("published DB unavailable: %s", reason)
                raise PublishedDbUnavailableError(
                    f"cannot load the published DB: {reason}"
                ) from exc
            # Windows: os.replace lên file đang có connection mở → PermissionError, cũng về đây
            logger.warning("published DB refresh failed, serving the previous copy: %s", reason)
        return self.local_path

    def _token(self, oidc_token: str | None) -> tuple[str, str]:
        """(token, nguồn) — nguồn chỉ để log chẩn đoán, không bao giờ log giá trị token.
        Header của request (trên Vercel) → biến môi trường (`vercel dev`, hoặc chạy chế độ này ở
        laptop bằng token đọc-ghi trong .env)."""
        for source, token in (
            ("header", oidc_token),
            ("env VERCEL_OIDC_TOKEN", os.environ.get("VERCEL_OIDC_TOKEN")),
            ("env BLOB_READ_WRITE_TOKEN", os.environ.get("BLOB_READ_WRITE_TOKEN")),
        ):
            if token:
                return token, source
        raise PublishedDbUnavailableError("no Blob credential (OIDC header or token)")

    def _refresh(self, oidc_token: str | None) -> None:
        if not self.store_id:
            raise PublishedDbUnavailableError(f"{STORE_ID_ENV} is not set")
        token, source = self._token(oidc_token)
        headers = {"Authorization": f"Bearer {token}"}
        if self._etag is not None and self._has_copy():
            headers["If-None-Match"] = self._etag
        self.local_dir.mkdir(parents=True, exist_ok=True)
        # tên riêng mỗi lần tải: 2 process cùng thư mục tạm (laptop) không ghi chồng cùng 1 file
        fd, part_name = tempfile.mkstemp(dir=self.local_dir, suffix=".part")
        os.close(fd)
        part = Path(part_name)
        try:
            with (
                httpx.Client(timeout=DOWNLOAD_TIMEOUT_S, transport=self.transport) as client,
                client.stream("GET", self.url, headers=headers) as resp,
            ):
                if resp.status_code == 304:
                    # 304 chỉ hợp lệ khi đã hỏi bằng ETag của bản đang có — không bao giờ thay
                    # cho lần tải đầu (proxy trả 304 sai → file sót sẽ bị phục vụ)
                    if "If-None-Match" not in headers:
                        raise PublishedDbUnavailableError("HTTP 304 without a conditional request")
                    return
                if resp.is_error:
                    raise PublishedDbUnavailableError(
                        f"Blob returned HTTP {resp.status_code} (credential from {source})"
                    )
                with part.open("wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
                etag = resp.headers.get("etag")
            with part.open("rb") as f:
                header = f.read(20)
            if header[:16] != SQLITE_HEADER:
                raise PublishedDbUnavailableError("downloaded blob is not an SQLite database")
            if header[18:20] != ROLLBACK_JOURNAL_FLAGS:
                raise PublishedDbUnavailableError("published copy is not in rollback-journal mode")
            # thay nguyên tử: connection đang mở giữ inode cũ, connection mới thấy bản mới
            os.replace(part, self.local_path)
            self._loaded = True
        finally:
            # tải dở / sai định dạng → không để lại file rác (đóng file xong mới xoá: Windows
            # không xoá được file đang mở)
            part.unlink(missing_ok=True)
        self._etag = etag
        logger.info(
            "published DB loaded (%d bytes, credential from %s)",
            self.local_path.stat().st_size,
            source,
        )
