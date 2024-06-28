from __future__ import annotations

from aiohttp import ClientSession

import json
from urllib.parse import urlparse
import sys
from typing import TYPE_CHECKING

from ..__version__ import __version__

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from aiohttp import ClientResponse
    from aiohttp.typedefs import JSONEncoder, JSONDecoder
    
    from typing import Any, Dict, Optional, Union


class BaseExchange:
    __slots__ = (
        "url",
        "_session",
        "_json_encoder",
        "_json_decoder"
    )

    def __init__(
        self,
        url: str,
        session: Optional[ClientSession] = None,
        json_encoder: JSONEncoder = json.dumps,
        json_decoder: JSONDecoder = json.loads
    ) -> None:
        self.url = url

        self._json_encoder = json_encoder
        self._json_decoder = json_decoder

        if session is None:
            self._session = ClientSession(
                json_serialize=self._json_encoder
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

        if data is not None:
            if not isinstance(data, str):
                data = self._json_encoder(data)
            headers["Content-Type"] = "application/json"

        async with self._session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            **request_kwargs
        ) as response:
            json_data = await response.json(
                encoding="utf-8",
                loads=self._json_decoder
            )

            self._handle_errors(response, json_data)

            response.raise_for_status()

            return json_data
    
    async def __aenter__(self) -> Self:
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self._session.close()
