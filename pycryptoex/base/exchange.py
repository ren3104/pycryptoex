from __future__ import annotations

from aiohttp import ClientSession

import abc
import asyncio
import sys
from typing import TYPE_CHECKING

from ..__version__ import __version__
from .utils import to_json, from_json

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from typing import Any, Optional

    from .websocket import BaseStreamManager


DEFAULT_HEADERS = {
    "Content-Type": "application/json;charset=utf-8",
    "User-Agent": "pycryptoex-" + __version__
}


class BaseExchange(metaclass=abc.ABCMeta):
    __slots__ = (
        "base_url",
        "_session"
    )

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._session: Optional[ClientSession] = None

    @property
    def closed(self) -> bool:
        return self._session is None or self._session.closed

    @property
    @abc.abstractmethod
    def authorized(self) -> bool:
        ...

    @abc.abstractmethod
    def _sign(
        self,
        path: str,
        params: Optional[dict[str, Any]],
        data: Optional[dict[str, Any]],
        headers: dict[str, Any],
        method: str
    ) -> tuple[Any, ...]:
        ...

    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        pass

    async def request(
        self,
        path: str,
        signed: bool = False,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        method: str = "GET",
        **request_kwargs: Any
    ) -> Any:
        if self._session is None or self._session.closed:
            raise RuntimeError("HTTP session is closed")

        if headers is None:
            headers = DEFAULT_HEADERS.copy()
        else:
            headers.update(DEFAULT_HEADERS)

        data_string: Optional[str] = None

        if signed:
            path, params, data_string, headers, method = self._sign(path, params, data, headers, method)

        if data_string is None and data:
            data_string = to_json(data)

        async with self._session.request(
            method=method,
            url=self.base_url + path,
            params=params,
            data=data_string,
            headers=headers,
            **request_kwargs
        ) as response:
            json_data = await response.json(
                encoding="utf-8",
                loads=from_json
            )

            self._handle_errors(response, json_data)

            response.raise_for_status()

            return json_data

    async def create_websocket_stream(self, private: bool = False) -> BaseStreamManager:
        raise NotImplementedError

    async def __aenter__(self) -> Self:
        if self.closed:
            self._session = ClientSession(json_serialize=to_json)

        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

            # Wait 250 ms for the underlying SSL connections to close
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0.25)
