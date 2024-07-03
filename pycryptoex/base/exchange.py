from __future__ import annotations

from aiohttp import ClientSession

from urllib.parse import urlparse
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
    
    from typing import Any, Dict, Optional, Union


class BaseExchange:
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
            self._session = ClientSession(
                json_serialize=to_json
            )

    def _sign(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        headers: Dict[str, Any] = {},
        method: str = "GET"
    ) -> None:
        raise NotImplementedError
    
    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        pass
    
    async def request(
        self,
        path: str,
        signed: bool = False,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        headers: Dict[str, Any] = {},
        method: str = "GET",
        **request_kwargs: Any
    ) -> Any:
        headers.update({
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "pycryptoex-" + __version__
        })

        if signed:
            self._sign(
                path=path,
                params=params,
                data=data,
                headers=headers,
                method=method
            )

        if len(urlparse(path).netloc) == 0:
            url = self.url + path
        else:
            url = path

        if data is not None and not isinstance(data, str):
            data = to_json(data)

        async with self._session.request(
            method=method,
            url=url,
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
    
    async def __aenter__(self) -> Self:
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self._session.close()
