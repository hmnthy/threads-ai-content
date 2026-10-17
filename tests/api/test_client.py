import pytest
import respx
from httpx import Response

from src.api.client import ThreadsAPIError, ThreadsClient


@respx.mock
async def test_get_returns_parsed_json_and_includes_access_token() -> None:
    route = respx.get("https://graph.threads.net/v1.0/123").mock(
        return_value=Response(200, json={"id": "123", "username": "thydilammuon"})
    )
    client = ThreadsClient(access_token="tok-abc")

    data = await client.get("/123", params={"fields": "id,username"})

    assert data == {"id": "123", "username": "thydilammuon"}
    assert route.calls.last.request.url.params["access_token"] == "tok-abc"
    await client.aclose()


@respx.mock
async def test_get_raises_threads_api_error_on_error_response() -> None:
    respx.get("https://graph.threads.net/v1.0/123").mock(
        return_value=Response(400, json={"error": {"message": "Invalid parameter", "code": 100}})
    )
    client = ThreadsClient(access_token="tok-abc")

    with pytest.raises(ThreadsAPIError) as exc_info:
        await client.get("/123")

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == 100
    assert "Invalid parameter" in str(exc_info.value)
    await client.aclose()


@respx.mock
async def test_error_message_carries_status_code_and_fbtrace_id_for_the_job_log() -> None:
    # Shape thật 2026-10-17: lỗi 5xx của Meta chỉ có message chung chung — log job chỉ in
    # str(lỗi), nên phải kèm HTTP status, code và fbtrace_id mới chẩn đoán được.
    respx.get("https://graph.threads.net/v1.0/123").mock(
        return_value=Response(
            500,
            json={
                "error": {
                    "message": "An unknown error has occurred.",
                    "type": "OAuthException",
                    "code": 1,
                    "fbtrace_id": "TRACE123",
                }
            },
        )
    )
    client = ThreadsClient(access_token="tok-abc")

    with pytest.raises(ThreadsAPIError) as exc_info:
        await client.get("/123")

    assert exc_info.value.fbtrace_id == "TRACE123"
    assert str(exc_info.value) == (
        "An unknown error has occurred. (HTTP 500, code 1, fbtrace_id TRACE123)"
    )
    assert "tok-abc" not in str(exc_info.value)
    await client.aclose()


@respx.mock
async def test_non_json_error_body_still_raises_threads_api_error() -> None:
    # Gateway 502 trả HTML: trước đây response.json() ném JSONDecodeError (không có
    # status_code) nên lớp phân trang không nhận ra đây là lỗi 5xx để thử lại.
    respx.get("https://graph.threads.net/v1.0/123").mock(
        return_value=Response(502, text="<html>Bad Gateway</html>")
    )
    client = ThreadsClient(access_token="tok-abc")

    with pytest.raises(ThreadsAPIError) as exc_info:
        await client.get("/123")

    assert exc_info.value.status_code == 502
    assert exc_info.value.error_code is None
    await client.aclose()


@respx.mock
async def test_client_usable_as_async_context_manager() -> None:
    respx.get("https://graph.threads.net/v1.0/ping").mock(return_value=Response(200, json={}))

    async with ThreadsClient(access_token="tok-abc") as client:
        data = await client.get("/ping")

    assert data == {}
