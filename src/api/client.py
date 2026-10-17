from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Final

import httpx

THREADS_GRAPH_BASE_URL: Final = "https://graph.threads.net/v1.0"

# Token đi trong query string; httpx log mỗi request kèm URL đầy đủ ở mức INFO. Ghim httpx ở
# WARNING để dù ai bật `logging.basicConfig(level=INFO)` token cũng không vào file log.
logging.getLogger("httpx").setLevel(logging.WARNING)


class ThreadsAPIError(RuntimeError):
    """Raised when the Threads Graph API returns an error payload."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_code: int | None = None,
        fbtrace_id: str | None = None,
    ) -> None:
        # Ghi kèm HTTP status + code + fbtrace_id vào chuỗi lỗi: log job chỉ in str(lỗi),
        # và "An unknown error has occurred." một mình không phân biệt được lỗi 5xx tạm
        # thời của Meta với lỗi token/tham số (bài học 2026-10-17).
        super().__init__(
            f"{message} (HTTP {status_code}, code {error_code}, fbtrace_id {fbtrace_id})"
        )
        self.status_code = status_code
        self.error_code = error_code
        self.fbtrace_id = fbtrace_id


class ThreadsClient:
    """Thin async wrapper around httpx for calling the Threads Graph API."""

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = THREADS_GRAPH_BASE_URL,
        timeout: float = 15.0,
    ) -> None:
        self._access_token = access_token
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.get(path, params=self._with_token(params))
        return self._parse(response)

    async def post(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.post(path, params=self._with_token(params))
        return self._parse(response)

    def _with_token(self, params: dict[str, Any] | None) -> dict[str, Any]:
        return {"access_token": self._access_token, **(params or {})}

    def _parse(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_error:
            # Lỗi 5xx từ gateway có thể là HTML, không phải JSON — vẫn phải ra
            # ThreadsAPIError (có status_code) để `_fetch_page` thử lại được
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            raise ThreadsAPIError(
                error.get("message", "Unknown Threads API error"),
                status_code=response.status_code,
                error_code=error.get("code"),
                fbtrace_id=error.get("fbtrace_id"),
            )
        payload: dict[str, Any] = response.json()
        return payload

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ThreadsClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
