from __future__ import annotations

import json
from urllib.parse import urlencode
import sys
if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from aiohttp.typedefs import JSONEncoder, JSONDecoder

    from typing import Any, Dict, Optional

from crypto_exchange.base.exchange import BaseExchange
from crypto_exchange.base.exceptions import AuthenticationError
from crypto_exchange.base.utils import current_timestamp, hmac_signature


class Bybit(BaseExchange):
    __slots__ = (
        "api_key",
        "secret",
        "recv_window",
        "timestamp_offset"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        recv_window: str = "5000",
        timestamp_offset: Optional[int] = None,
        url: str = "https://api.bytick.com",
        session: Optional[ClientSession] = None,
        json_encoder: JSONEncoder = json.dumps,
        json_decoder: JSONDecoder = json.loads
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.recv_window = recv_window
        self.timestamp_offset = timestamp_offset

        super().__init__(
            url=url,
            session=session,
            json_encoder=json_encoder,
            json_decoder=json_decoder
        )

    def _sign(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> None:
        if self.api_key is None:
            raise AuthenticationError("api_key")
        elif self.secret is None:
            raise AuthenticationError("secret")

        if params is None:
            params = {}
        if headers is None:
            headers = {}

        headers["X-BAPI-API-KEY"] = self.api_key
        headers["X-BAPI-SIGN"] = hmac_signature(
            key=self.secret,
            msg=urlencode(params)
        )
        headers["X-BAPI-TIMESTAMP"] = str(current_timestamp() + (self.timestamp_offset or 0))
        headers["X-BAPI-RECV-WINDOW"] = self.recv_window
    
    async def __aenter__(self) -> Self:
        if self.timestamp_offset is None:
            server_time: int = (await self.request("/v5/market/time"))["time"]
            self.timestamp_offset = server_time - current_timestamp()

        return self
