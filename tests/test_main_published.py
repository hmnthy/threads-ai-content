"""API ở chế độ chỉ đọc trên bản sao DB publish (ADR-0025 bước 2): middleware tải bản sao trước
khi xử lý request, `_db()` mở `mode=ro`, lỗi tải lần đầu → 503 vẫn có header CORS."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from src.db.published import PublishedDb
from tests.test_main import _seed_full_db


class _Blob:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body, self.status = body, status
        self.auth: list[str | None] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.auth.append(request.headers.get("authorization"))
        if self.status != 200:
            return httpx.Response(self.status)
        return httpx.Response(200, content=self.body, headers={"etag": '"v1"'})


def _published(tmp_path: Path, blob: _Blob) -> PublishedDb:
    return PublishedDb(
        blob_path="threads.db",
        store_id="store_test",
        local_dir=tmp_path / "copy",
        transport=httpx.MockTransport(blob.handler),
    )


@pytest.fixture
def seeded_bytes(tmp_path: Path) -> bytes:
    src = tmp_path / "laptop.db"
    _seed_full_db(src)
    return src.read_bytes()


@pytest.fixture(autouse=True)
def _local_db_must_not_be_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    # chế độ publish không được đụng DB local: trỏ nó tới chỗ không tồn tại và kiểm sau test
    local = tmp_path / "local" / "threads.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", local)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    yield local
    assert not local.parent.exists()


def test_regular_test_run_reads_the_local_db() -> None:
    # `.env` (load_dotenv lúc import) có thể chứa DB_BLOB_PATH cho bước publish — bộ test thường
    # không bao giờ được chạy ở chế độ Blob (sẽ gọi Blob thật)
    assert main_module._PUBLISHED is None


def test_serves_published_copy_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seeded_bytes: bytes
) -> None:
    blob = _Blob(seeded_bytes)
    monkeypatch.setattr(main_module, "_PUBLISHED", _published(tmp_path, blob))

    resp = TestClient(main_module.app).get(
        "/content-units", headers={"x-vercel-oidc-token": "oidc-1"}
    )

    assert resp.status_code == 200
    assert [u["id"] for u in resp.json()] == ["post-1"]
    assert blob.auth == ["Bearer oidc-1"]


def test_health_does_not_depend_on_the_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blob = _Blob(b"", status=403)
    monkeypatch.setattr(main_module, "_PUBLISHED", _published(tmp_path, blob))

    resp = TestClient(main_module.app).get("/health")

    assert resp.status_code == 200
    assert blob.auth == []  # không gọi Blob


def test_first_load_failure_returns_503_with_cors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blob = _Blob(b"", status=403)
    monkeypatch.setattr(main_module, "_PUBLISHED", _published(tmp_path, blob))

    resp = TestClient(main_module.app).get(
        "/content-units",
        headers={"x-vercel-oidc-token": "bad", "Origin": "http://localhost:3000"},
    )

    assert resp.status_code == 503
    assert resp.json() == {"detail": "Data is temporarily unavailable."}
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
