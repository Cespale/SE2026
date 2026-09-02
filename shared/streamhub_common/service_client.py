import asyncio
import os
from typing import Any

import httpx


class ServiceUnavailable(RuntimeError):
    pass


class ServiceClient:
    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        connect_timeout = float(os.getenv("SERVICE_CONNECT_TIMEOUT_SECONDS", "0.5"))
        total_timeout = float(os.getenv("SERVICE_TOTAL_TIMEOUT_SECONDS", "1.5"))
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(total_timeout, connect=connect_timeout),
            transport=transport,
        )

    async def request_json(
        self,
        method: str,
        path: str,
        request_id: str,
        **kwargs: Any,
    ) -> Any:
        normalized_method = method.upper()
        max_attempts = 3 if normalized_method in {"GET", "HEAD"} else 1
        headers = dict(kwargs.pop("headers", {}))
        headers["X-Request-ID"] = request_id
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                response = await self._client.request(
                    normalized_method,
                    path,
                    headers=headers,
                    **kwargs,
                )
                if response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                last_error = RuntimeError(
                    f"upstream status {response.status_code}"
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

            if attempt + 1 < max_attempts:
                await asyncio.sleep(0.05 * (2**attempt))

        raise ServiceUnavailable(str(last_error))

    async def aclose(self) -> None:
        await self._client.aclose()
