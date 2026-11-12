"""Endpoint phát file demo RAG (ADR-0037 D3): chỉ tên trong danh sách cố định, phát nguyên byte, có
header cache; trên Vercel không phụ thuộc bản sao DB."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import src.db.published_demo as demo_module
import src.main as main_module
from src.db.published import PublishedDb
from src.db.published_demo import CACHE_CONTROL, PublishedDemo, etag_of

BODY = '{"format": 1, "units": [{"id": "1", "text": "Chủ nhà 🏠"}]}'.encode()


@pytest.fixture
def local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "demo.json"
    monkeypatch.setitem(demo_module.LOCAL_FILES, "common", path)
    monkeypatch.setattr(main_module, "_PUBLISHED_DEMO", None)
    return path


def test_regular_test_run_reads_the_local_file() -> None:
    assert main_module._PUBLISHED_DEMO is None


def test_serves_the_built_file_byte_for_byte_with_cache_headers(local_file: Path) -> None:
    local_file.write_bytes(BODY)
    resp = TestClient(main_module.app).get("/rag-demo/common")
    assert resp.status_code == 200
    assert resp.content == BODY
    assert resp.headers["content-type"] == "application/json"
    assert resp.headers["cache-control"] == CACHE_CONTROL
    assert resp.headers["etag"] == etag_of(BODY)
    assert resp.headers["vary"] == "Origin"  # cả khi request không có Origin


@pytest.mark.parametrize("name", ["q01", "threads.db", "common.json", "..%2Fthreads.db", "COMMON"])
def test_names_outside_the_list_are_404_before_any_read(local_file: Path, name: str) -> None:
    local_file.write_bytes(BODY)
    resp = TestClient(main_module.app).get(f"/rag-demo/{name}")
    assert resp.status_code == 404


def test_not_built_yet_is_a_503_with_cors(local_file: Path) -> None:
    resp = TestClient(main_module.app).get(
        "/rag-demo/common", headers={"origin": "http://localhost:3000"}
    )
    assert resp.status_code == 503
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert str(local_file) not in resp.text  # chi tiết chỉ ở log


def test_a_broken_local_file_is_a_503(local_file: Path) -> None:
    local_file.write_bytes(b'{"format": 1')
    assert TestClient(main_module.app).get("/rag-demo/common").status_code == 503


def test_on_vercel_the_demo_never_waits_for_the_db_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bản sao DB tải lỗi (Blob trả 500) mà file demo vẫn phát: middleware bỏ qua route này."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/rag-demo/common.json"):
            return httpx.Response(200, content=BODY, headers={"etag": '"v1"'})
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        main_module,
        "_PUBLISHED",
        PublishedDb(
            blob_path="threads.db",
            store_id="store_t",
            local_dir=tmp_path / "copy",
            transport=transport,
        ),
    )
    monkeypatch.setattr(
        main_module, "_PUBLISHED_DEMO", PublishedDemo(store_id="store_t", transport=transport)
    )
    client = TestClient(main_module.app)
    resp = client.get("/rag-demo/common", headers={"x-vercel-oidc-token": "oidc"})
    assert resp.status_code == 200
    assert resp.content == BODY
    assert seen == ["/rag-demo/common.json"]
    # đối chứng: route đọc DB vẫn đi qua bản sao DB (và 503 vì Blob lỗi)
    assert client.get("/topics", headers={"x-vercel-oidc-token": "oidc"}).status_code == 503


def test_no_shared_cache_may_keep_a_response_without_cors_headers(local_file: Path) -> None:
    """Header CORS chỉ có khi `Origin` được phép: CDN giữ bản của request không có `Origin` (mở
    thẳng link, bot) thì mọi trình duyệt khác bị lỗi CORS tới khi hết hạn → cấm cache dùng chung."""
    local_file.write_bytes(BODY)
    resp = TestClient(main_module.app).get("/rag-demo/common")  # không có Origin
    assert "access-control-allow-origin" not in resp.headers
    cache_control = {part.strip() for part in resp.headers["cache-control"].split(",")}
    assert "private" in cache_control
    assert not any(part.startswith("s-maxage") for part in cache_control)
    assert "public" not in cache_control


@pytest.mark.parametrize(
    "if_none_match",
    [lambda tag: tag, lambda tag: f"W/{tag}", lambda tag: f'"cu", {tag}', lambda tag: "*"],
)
def test_matching_etag_is_a_304_without_body(
    local_file: Path, if_none_match: Callable[[str], str]
) -> None:
    local_file.write_bytes(BODY)
    resp = TestClient(main_module.app).get(
        "/rag-demo/common", headers={"if-none-match": if_none_match(etag_of(BODY))}
    )
    assert resp.status_code == 304
    assert resp.content == b""
    assert resp.headers["etag"] == etag_of(BODY)


def test_an_old_etag_gets_the_new_file(local_file: Path) -> None:
    local_file.write_bytes(BODY)
    resp = TestClient(main_module.app).get(
        "/rag-demo/common", headers={"if-none-match": etag_of(b"ban cu")}
    )
    assert resp.status_code == 200
    assert resp.content == BODY


def test_a_304_keeps_the_cors_headers(local_file: Path) -> None:
    local_file.write_bytes(BODY)
    resp = TestClient(main_module.app).get(
        "/rag-demo/common",
        headers={"if-none-match": etag_of(BODY), "origin": "http://localhost:3000"},
    )
    assert resp.status_code == 304
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
