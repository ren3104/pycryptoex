from __future__ import annotations

from urllib.parse import urlencode
import sys
from typing import TYPE_CHECKING

from pycryptoex.base.exchange import BaseExchange
from pycryptoex.base.exceptions import AuthenticationError, ExchangeApiError
from pycryptoex.base.utils import current_timestamp, hmac_signature

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from typing import Any, Optional


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
        base_url: str = "https://api.bybit.com"
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.recv_window = recv_window
        self.timestamp_offset = timestamp_offset

        super().__init__(base_url)

    @property
    def authorized(self) -> bool:
        return not (
            self.api_key is None
            or self.secret is None
        )

    def _sign(
        self,
        path: str,
        params: Optional[dict[str, Any]],
        data: Optional[dict[str, Any]],
        headers: dict[str, Any],
        method: str
    ) -> tuple[Any, ...]:
        if self.api_key is None:
            raise AuthenticationError("api_key")
        elif self.secret is None:
            raise AuthenticationError("secret")

        headers["X-BAPI-API-KEY"] = self.api_key
        headers["X-BAPI-SIGN"] = hmac_signature(
            key=self.secret,
            msg="" if params is None else urlencode(params)
        )
        headers["X-BAPI-TIMESTAMP"] = str(current_timestamp() + (self.timestamp_offset or 0))
        headers["X-BAPI-RECV-WINDOW"] = self.recv_window

        return path, params, None, headers, method

    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        if isinstance(json_data, dict):
            code = json_data.get("retCode")
            if code != 0:
                msg = json_data.get("retMsg")
                if msg is not None:
                    raise ExchangeApiError(code, msg)

    async def __aenter__(self) -> Self:
        await super().__aenter__()

        if self.timestamp_offset is None:
            server_time: int = (await self.request("/v5/market/time"))["time"]
            self.timestamp_offset = server_time - current_timestamp()

        return self
