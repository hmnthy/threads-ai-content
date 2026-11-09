"""File demo RAG publish (ADR-0037 D3): tải từ Blob riêng tư, hỏi lại theo ETag, chỉ tên trong danh
sách cố định. HTTP giả bằng `httpx.MockTransport` — không gọi mạng."""

from __future__ import annotations

import threading

import httpx
import pytest

from src.db.published import RETRY_WITHOUT_COPY_S
from src.db.published_demo import (
    LOCAL_FILES,
    REVALIDATE_S,
    DemoFileUnavailableError,
    PublishedDemo,
    blob_pathname,
    check_demo_bytes,
)
from src.rag_demo.demo_file import DEMO_PATH

GOOD = b'{"format": 1, "units": []}'
NEWER = b'{"format": 1, "units": [{"id": "x"}]}'


class FakeBlob:
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


def _demo(blob: FakeBlob, clock: Clock) -> PublishedDemo:
    return PublishedDemo(
        store_id="store_ABC", clock=clock, transport=httpx.MockTransport(blob.handler)
    )


def test_local_path_matches_the_build_step() -> None:
    # API không import `src/rag_demo/` (gói Vercel) nên giữ bản sao của đường dẫn — phải khớp
    assert LOCAL_FILES["common"] == DEMO_PATH


def test_only_listed_names_map_to_a_pathname() -> None:
    assert blob_pathname("common") == "rag-demo/common.json"
    for name in ("q01", "../threads", "threads.db", "common.json", ""):
        with pytest.raises(KeyError):
            blob_pathname(name)


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b'{"format": "1"}', b"{"])
def test_a_body_that_is_not_a_demo_file_is_refused(body: bytes) -> None:
    with pytest.raises(DemoFileUnavailableError):
        check_demo_bytes(body)


def test_first_load_reads_the_fixed_pathname_with_the_request_token() -> None:
    blob = FakeBlob(GOOD)
    demo = _demo(blob, Clock())
    assert demo.get("common", "oidc-1") == GOOD
    (request,) = blob.requests
    assert str(request.url) == "https://abc.private.blob.vercel-storage.com/rag-demo/common.json"
    assert request.headers["authorization"] == "Bearer oidc-1"
    assert "if-none-match" not in request.headers


def test_serves_from_memory_until_revalidation_then_uses_the_etag() -> None:
    blob, clock = FakeBlob(GOOD), Clock()
    demo = _demo(blob, clock)
    demo.get("common", "t")
    clock.t += REVALIDATE_S - 1
    assert demo.get("common", "t") == GOOD
    assert len(blob.requests) == 1
    clock.t += 2
    assert demo.get("common", "t") == GOOD  # 304
    assert blob.requests[-1].headers["if-none-match"] == '"v1"'
    blob.body, blob.etag = NEWER, '"v2"'
    clock.t += REVALIDATE_S
    assert demo.get("common", "t") == NEWER


def test_failed_refresh_keeps_serving_the_previous_copy() -> None:
    blob, clock = FakeBlob(GOOD), Clock()
    demo = _demo(blob, clock)
    demo.get("common", "t")
    blob.status = 500
    clock.t += REVALIDATE_S
    assert demo.get("common", "t") == GOOD


def test_a_broken_body_never_replaces_the_previous_copy() -> None:
    blob, clock = FakeBlob(GOOD), Clock()
    demo = _demo(blob, clock)
    demo.get("common", "t")
    blob.body, blob.etag = b"<html>proxy error</html>", '"v2"'
    clock.t += REVALIDATE_S
    assert demo.get("common", "t") == GOOD


def test_first_load_failure_is_unavailable_and_waits_before_a_retry() -> None:
    blob, clock = FakeBlob(GOOD, status=403), Clock()
    demo = _demo(blob, clock)
    with pytest.raises(DemoFileUnavailableError):
        demo.get("common", "t")
    blob.status = 200
    with pytest.raises(DemoFileUnavailableError, match="waiting"):
        demo.get("common", "t")
    assert len(blob.requests) == 1
    clock.t += RETRY_WITHOUT_COPY_S
    assert demo.get("common", "t") == GOOD  # lần gọi thứ hai sau 1 lần lỗi


def test_a_304_on_the_first_load_is_never_trusted() -> None:
    class AlwaysNotModified(FakeBlob):
        def handler(self, request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(304)

    demo = _demo(AlwaysNotModified(GOOD), Clock())
    with pytest.raises(DemoFileUnavailableError):
        demo.get("common", "t")


def test_missing_store_id_or_credential_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = FakeBlob(GOOD)
    no_store = PublishedDemo(store_id="", transport=httpx.MockTransport(blob.handler))
    with pytest.raises(DemoFileUnavailableError):
        no_store.get("common", "t")
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    with pytest.raises(DemoFileUnavailableError):
        _demo(blob, Clock()).get("common", None)
    assert blob.requests == []


def test_only_enabled_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    assert PublishedDemo.from_env() is None
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("BLOB_STORE_ID", "store_X")
    demo = PublishedDemo.from_env()
    assert demo is not None
    assert demo.store_id == "store_X"


def test_other_requests_get_the_old_copy_while_one_refreshes() -> None:
    """Chỉ một luồng tải; luồng khác không chờ Blob chậm mà nhận ngay bản đang có."""
    started, release = threading.Event(), threading.Event()
    blob, clock = FakeBlob(GOOD), Clock()

    def slow(request: httpx.Request) -> httpx.Response:
        if blob.requests:  # lần làm mới: treo tới khi test cho chạy tiếp
            started.set()
            assert release.wait(timeout=10)
        return blob.handler(request)

    demo = PublishedDemo(store_id="store_ABC", clock=clock, transport=httpx.MockTransport(slow))
    demo.get("common", "t")
    blob.body, blob.etag = NEWER, '"v2"'
    clock.t += REVALIDATE_S
    refreshed: list[bytes] = []
    worker = threading.Thread(target=lambda: refreshed.append(demo.get("common", "t")))
    worker.start()
    try:
        assert started.wait(timeout=10)
        assert demo.get("common", "t") == GOOD  # không chờ khoá
    finally:
        release.set()
        worker.join(timeout=10)
    assert refreshed == [NEWER]


def test_a_404_means_removed_and_drops_the_copy_in_memory() -> None:
    """Gỡ gấp = xoá object trên Blob: 404 không được coi là lỗi tạm rồi phát tiếp bản cũ."""
    blob, clock = FakeBlob(GOOD), Clock()
    demo = _demo(blob, clock)
    demo.get("common", "t")
    blob.status = 404
    clock.t += REVALIDATE_S
    with pytest.raises(DemoFileUnavailableError):
        demo.get("common", "t")
    clock.t += 1  # trong lúc chờ thử lại cũng không được rơi về bản cũ
    with pytest.raises(DemoFileUnavailableError):
        demo.get("common", "t")
    blob.status = 200
    clock.t += RETRY_WITHOUT_COPY_S
    assert demo.get("common", "t") == GOOD  # publish lại thì phát lại
