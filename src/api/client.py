from __future__ import annotations

from types import TracebackType
from typing import Any, Final

import httpx

THREADS_GRAPH_BASE_URL: Final = "https://graph.threads.net/v1.0"


class ThreadsAPIError(RuntimeError):
    """Raised when the Threads Graph API returns an error payload."""

    def __init__(self, message: str, *, status_code: int, error_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


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

    async def get_url(self, url: str) -> dict[str, Any]:
        """Fetch an absolute URL as-is — used for a Graph API `paging.next` cursor
        link, which already carries the access token and all query params."""
        response = await self._http.get(url)
        return self._parse(response)

    async def post(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.post(path, params=self._with_token(params))
        return self._parse(response)

    def _with_token(self, params: dict[str, Any] | None) -> dict[str, Any]:
        return {"access_token": self._access_token, **(params or {})}

    def _parse(self, response: httpx.Response) -> dict[str, Any]:
        payload: dict[str, Any] = response.json()
        if response.is_error:
            error = payload.get("error", {})
            raise ThreadsAPIError(
                error.get("message", "Unknown Threads API error"),
                status_code=response.status_code,
                error_code=error.get("code"),
            )
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
