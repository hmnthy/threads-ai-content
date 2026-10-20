"""Bản sao DB publish — tải từ Blob riêng tư, hỏi lại theo ETag, mở chỉ đọc (ADR-0025 bước 2).
HTTP giả bằng `httpx.MockTransport` bơm vào `PublishedDb.transport` — không gọi mạng."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest

import src.db.published as published_module
from src.db.published import (
    RETRY_WITHOUT_COPY_S,
    REVALIDATE_S,
    PublishedDb,
    PublishedDbUnavailableError,
)
from src.db.schema import connect, connect_readonly, create_schema


def _sqlite_bytes(tmp_path: Path, name: str, marker: str) -> bytes:
    """File SQLite thật có 1 bảng đánh dấu phiên bản — để biết bản nào đang được phục vụ."""
    path = tmp_path / name
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE marker (v TEXT)")
    conn.execute("INSERT INTO marker VALUES (?)", (marker,))
    conn.commit()
    conn.close()
    return path.read_bytes()


def _served_marker(db: PublishedDb) -> str:
    conn = connect_readonly(db.local_path)
    try:
        return str(conn.execute("SELECT v FROM marker").fetchone()[0])
    finally:
        conn.close()


class FakeBlob:
    """Blob store giả: trả `body` kèm ETag, 304 khi `If-None-Match` khớp, ghi lại mọi request."""

    def __init__(self, body: bytes, etag: str = '"v1"', status: int = 200) -> None:
        self.body, self.etag, self.status = body, etag, status
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status)
        if request.headers.get("if-none-match") == self.etag:
            return httpx.Response(304)
        return httpx.Response(200, content=self.body, headers={"etag": self.etag})


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _db(tmp_path: Path, blob: FakeBlob, clock: Clock | None = None) -> PublishedDb:
    return PublishedDb(
        blob_path="db/threads.db",
        store_id="store_AbC123",
        local_dir=tmp_path / "tmp-copy",
        clock=clock or Clock(),
        transport=httpx.MockTransport(blob.handler),
    )


@pytest.fixture(autouse=True)
def _no_env_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env của máy có thể có BLOB_READ_WRITE_TOKEN (bước publish) — test không được dựa vào nó
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)


def test_first_request_downloads_with_bearer_token_from_private_store(tmp_path: Path) -> None:
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob)

    path = db.ensure("oidc-abc")

    assert path == db.local_path and _served_marker(db) == "v1"
    (req,) = blob.requests
    # `store_` bỏ, chữ thường; pathname giữ nguyên
    assert str(req.url) == "https://abc123.private.blob.vercel-storage.com/db/threads.db"
    assert req.headers["authorization"] == "Bearer oidc-abc"
    assert "if-none-match" not in req.headers


def test_within_revalidate_window_no_request(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob, clock)
    db.ensure("t")

    clock.t += REVALIDATE_S - 1
    db.ensure("t")

    assert len(blob.requests) == 1


def test_after_window_revalidates_with_etag_and_keeps_copy_on_304(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob, clock)
    db.ensure("t")
    mtime = db.local_path.stat().st_mtime_ns

    clock.t += REVALIDATE_S
    db.ensure("t")

    assert len(blob.requests) == 2
    assert blob.requests[1].headers["if-none-match"] == '"v1"'
    assert db.local_path.stat().st_mtime_ns == mtime  # 304 → không ghi lại file
    assert list(db.local_dir.glob("*.part")) == []  # file tạm tạo trước request cũng được dọn


def test_new_publish_replaces_copy(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob, clock)
    db.ensure("t")

    blob.body, blob.etag = _sqlite_bytes(tmp_path, "b.db", "v2"), '"v2"'
    clock.t += REVALIDATE_S
    db.ensure("t")

    assert _served_marker(db) == "v2"
    assert list(db.local_dir.glob("*.part")) == []


def test_refresh_failure_keeps_previous_copy_and_waits_a_window(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob, clock)
    db.ensure("t")

    blob.status = 403  # token hết hạn / sai
    clock.t += REVALIDATE_S
    db.ensure("t")
    db.ensure("t")  # cùng thời điểm: không thử lại ngay

    assert _served_marker(db) == "v1"
    assert len(blob.requests) == 2


def test_non_sqlite_body_never_replaces_good_copy(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob, clock)
    db.ensure("t")

    blob.body, blob.etag = b"<html>error</html>", '"v2"'
    clock.t += REVALIDATE_S
    db.ensure("t")

    assert _served_marker(db) == "v1"
    assert list(db.local_dir.glob("*.part")) == []


@pytest.mark.parametrize(
    ("status", "body"),
    [(403, b""), (404, b""), (200, b"not a database")],
)
def test_first_load_failure_raises_unavailable(tmp_path: Path, status: int, body: bytes) -> None:
    blob = FakeBlob(body, status=status)
    db = _db(tmp_path, blob)

    with pytest.raises(PublishedDbUnavailableError):
        db.ensure("t")
    assert not db.local_path.exists()


def test_failed_first_load_backs_off_before_retrying(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(b"", status=403)
    db = _db(tmp_path, blob, clock)
    with pytest.raises(PublishedDbUnavailableError):
        db.ensure("t")

    clock.t += RETRY_WITHOUT_COPY_S - 1
    with pytest.raises(PublishedDbUnavailableError, match="waiting"):
        db.ensure("t")
    assert len(blob.requests) == 1  # trong khoảng chờ: 503 ngay, không gọi Blob

    blob.body, blob.status = _sqlite_bytes(tmp_path, "a.db", "v1"), 200
    clock.t += 1
    db.ensure("t")
    assert len(blob.requests) == 2 and _served_marker(db) == "v1"


def test_no_credential_raises_without_request(tmp_path: Path) -> None:
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob)

    with pytest.raises(PublishedDbUnavailableError, match="credential"):
        db.ensure(None)
    assert blob.requests == []


def test_env_token_is_fallback_for_missing_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "rw-token")
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob)

    db.ensure(None)

    assert blob.requests[0].headers["authorization"] == "Bearer rw-token"


def test_missing_store_id_raises(tmp_path: Path) -> None:
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob)
    db.store_id = ""

    with pytest.raises(PublishedDbUnavailableError, match="BLOB_STORE_ID"):
        db.ensure("t")


def test_from_env_only_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_BLOB_PATH", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert PublishedDb.from_env() is None

    monkeypatch.setenv("DB_BLOB_PATH", " db/threads.db ")
    monkeypatch.setenv("BLOB_STORE_ID", "store_x")
    db = PublishedDb.from_env()
    assert db is not None and (db.blob_path, db.store_id) == ("db/threads.db", "store_x")

    # laptop: `.env` có DB_BLOB_PATH cho bước publish nhưng không có VERCEL → vẫn đọc DB local
    monkeypatch.delenv("VERCEL")
    assert PublishedDb.from_env() is None


def test_wal_flagged_copy_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "wal.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE marker (v TEXT)")
    conn.commit()
    conn.close()
    body = path.read_bytes()
    assert body[18:20] == b"\x02\x02"  # dữ liệu test thật sự mang cờ WAL

    db = _db(tmp_path, FakeBlob(body))
    with pytest.raises(PublishedDbUnavailableError, match="rollback-journal"):
        db.ensure("t")
    assert not db.local_path.exists()


def test_unexpected_error_becomes_unavailable(tmp_path: Path) -> None:
    # token không phải ASCII → httpx ném UnicodeEncodeError khi dựng header; phải thành 503
    # (PublishedDbUnavailableError), không lọt ra thành 500 không có CORS
    db = _db(tmp_path, FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1")))

    with pytest.raises(PublishedDbUnavailableError, match="UnicodeEncodeError"):
        db.ensure("tôken")


def _with_leftover(tmp_path: Path, blob: FakeBlob, clock: Clock) -> PublishedDb:
    db = _db(tmp_path, blob, clock)
    db.local_dir.mkdir(parents=True)
    db.local_path.write_bytes(_sqlite_bytes(tmp_path, "old.db", "v0"))
    return db


def test_leftover_file_from_previous_process_is_never_served(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(b"", status=403)
    db = _with_leftover(tmp_path, blob, clock)

    with pytest.raises(PublishedDbUnavailableError):
        db.ensure("t")
    # lần gọi thứ 2 sau 1 lần thất bại: mốc "đã thử" đã đặt nhưng chưa tải được → vẫn 503
    clock.t += 1
    with pytest.raises(PublishedDbUnavailableError):
        db.ensure("t")
    clock.t += RETRY_WITHOUT_COPY_S
    with pytest.raises(PublishedDbUnavailableError):
        db.ensure("t")


def test_unconditional_304_never_stands_in_for_a_first_load(tmp_path: Path) -> None:
    # proxy/CDN trả 304 cho request không có If-None-Match → không được coi file sót là bản sao
    db = _with_leftover(tmp_path, FakeBlob(b"", status=304), Clock())

    with pytest.raises(PublishedDbUnavailableError, match="304"):
        db.ensure("t")


def test_leftover_file_not_served_while_first_load_is_in_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(published_module, "DOWNLOAD_TIMEOUT_S", 0.05)
    clock = Clock()
    blob = FakeBlob(b"", status=403)
    db = _with_leftover(tmp_path, blob, clock)
    with pytest.raises(PublishedDbUnavailableError):
        db.ensure("t")  # mốc "đã thử" đã đặt

    db._lock.acquire()  # giả lập 1 luồng khác đang tải lần đầu
    try:
        with pytest.raises(PublishedDbUnavailableError, match="timed out"):
            db.ensure("t")
    finally:
        db._lock.release()


def test_busy_lock_serves_previous_copy_without_waiting(tmp_path: Path) -> None:
    clock = Clock()
    blob = FakeBlob(_sqlite_bytes(tmp_path, "a.db", "v1"))
    db = _db(tmp_path, blob, clock)
    db.ensure("t")
    clock.t += REVALIDATE_S  # tới hạn hỏi lại

    db._lock.acquire()  # giả lập 1 luồng khác đang tải
    try:
        assert db.ensure("t") == db.local_path
    finally:
        db._lock.release()
    assert len(blob.requests) == 1  # không chờ, không tải thêm


def test_connect_readonly_rejects_writes(tmp_path: Path) -> None:
    path = tmp_path / "copy.db"
    conn = connect(path)
    create_schema(conn)
    conn.close()

    ro = connect_readonly(path)
    try:
        assert ro.execute("SELECT count(*) FROM posts").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ro.execute("CREATE TABLE x (a INTEGER)")
    finally:
        ro.close()


def test_connect_readonly_never_creates_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "threads.db"

    with pytest.raises(sqlite3.OperationalError):
        connect_readonly(missing)
    assert not missing.parent.exists()
