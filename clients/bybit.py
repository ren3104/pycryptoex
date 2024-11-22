from __future__ import annotations

try:
    from Crypto.PublicKey import RSA # type: ignore
except ModuleNotFoundError:
    pass

from urllib.parse import urlencode
import sys
from typing import TYPE_CHECKING

from pycryptoex.base.exchange import BaseExchange
from pycryptoex.base.exceptions import AuthenticationError, ExchangeApiError
from pycryptoex.base.utils import (
    to_json,
    current_timestamp,
    hmac_signature,
    rsa_signature
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from pathlib import Path
    from typing import Any, Optional, Union


class Bybit(BaseExchange):
    __slots__ = (
        "recv_window",
        "timestamp_offset"
    )

    DEFAULT_URL = "https://api.bybit.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        private_key: Optional[Union[str, Path]] = None,
        private_key_pass: Optional[str] = None,
        base_url: Optional[str] = None,
        recv_window: str = "5000",
        timestamp_offset: Optional[int] = None
    ) -> None:
        self.recv_window = recv_window
        self.timestamp_offset = timestamp_offset

        super().__init__(
            api_key,
            secret,
            passphrase,
            private_key,
            private_key_pass,
            base_url
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
            raise AuthenticationError

        params_string: Optional[str] = None
        data_string: Optional[str] = None
        if params:
            params_string = urlencode(params)
            path += "?" + params_string
            params.clear()
        elif data:
            params_string = data_string = to_json(data)

        timestamp = str(current_timestamp() + (self.timestamp_offset or 0))

        auth_string = timestamp + self.api_key + self.recv_window + (params_string or "")
        if self.private_key is not None and isinstance(self.private_key, RSA.RsaKey):
            signature = rsa_signature(self.private_key, auth_string)
        elif self.secret is not None:
            signature = hmac_signature(self.secret, auth_string)
        else:
            raise AuthenticationError

        headers["X-BAPI-API-KEY"] = self.api_key
        headers["X-BAPI-SIGN"] = signature
        headers["X-BAPI-SIGN-TYPE"] = "2"
        headers["X-BAPI-TIMESTAMP"] = timestamp
        headers["X-BAPI-RECV-WINDOW"] = self.recv_window

        return path, params, data_string, headers, method

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
