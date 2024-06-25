from __future__ import annotations

from aiohttp import ClientSession

import json
from urllib.parse import urlparse
import sys
if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp.typedefs import JSONEncoder, JSONDecoder

    from typing import Any, Dict, Optional


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
        headers: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> None:
        raise NotImplementedError
    
    def _handle_response_data(self, data: Any) -> Any:
        return data
    
    async def request(
        self,
        path: str,
        signed: bool = False,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        **request_kwargs: Any
    ) -> Any:
        headers.update({
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "crypto-exchange-client"
        })

        if signed:
            self._sign(
                path=path,
                params=params,
                headers=headers,
                method=method
            )

        if len(urlparse(path).netloc) == 0:
            url = self.url + path
        else:
            url = path

        async with self._session.request(
            method=method,
            url=url,
            params=params,
            raise_for_status=True,
            **request_kwargs
        ) as response:
            data = await response.json(
                encoding="utf-8",
                loads=self._json_decoder
            )

            return self._handle_response_data(data)
    
    async def __aenter__(self) -> Self:
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self._session.close()
