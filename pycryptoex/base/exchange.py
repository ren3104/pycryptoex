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
    
    from typing import Any, Optional, Union

    from .websocket import BaseStreamManager


class BaseExchange(metaclass=abc.ABCMeta):
    __slots__ = (
        "url",
        "_session"
    )

    def __init__(
        self,
        url: str,
        session: Optional[ClientSession] = None
    ) -> None:
        self.url = url

        if session is None:
            session = ClientSession(
                json_serialize=to_json
            )
        self._session = session

    @property
    @abc.abstractmethod
    def authorized(self) -> bool:
        ...

    @abc.abstractmethod
    def _sign(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[Union[dict[str, Any], str]] = None,
        headers: dict[str, Any] = {},
        method: str = "GET"
    ) -> tuple[Any, ...]:
        ...
    
    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        pass
    
    async def request(
        self,
        path: str,
        signed: bool = False,
        params: Optional[dict[str, Any]] = None,
        data: Optional[Union[dict[str, Any], str]] = None,
        headers: dict[str, Any] = {},
        method: str = "GET",
        **request_kwargs: Any
    ) -> Any:
        headers.update({
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "pycryptoex-" + __version__
        })

        if signed:
            path, params, data, headers, method = self._sign(path, params, data, headers, method)

        if data is not None and not isinstance(data, str):
            data = to_json(data)

        async with self._session.request(
            method=method,
            url=self.url + path,
            params=params,
            data=data,
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
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self._session.close()

        # Wait 250 ms for the underlying SSL connections to close
        # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
        await asyncio.sleep(0.25)
