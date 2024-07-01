from __future__ import annotations

from urllib.parse import urlencode
import json
from typing import TYPE_CHECKING

from pycryptoex.base.exchange import BaseExchange
from pycryptoex.base.exceptions import AuthenticationError, ExchangeApiError
from pycryptoex.base.utils import current_timestamp, hmac_signature

if TYPE_CHECKING:
    from aiohttp import ClientSession, ClientResponse
    from aiohttp.typedefs import JSONEncoder, JSONDecoder

    from typing import Any, Dict, Optional, Union


class KuCoin(BaseExchange):
    __slots__ = (
        "api_key",
        "secret",
        "passphrase"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        url: str = "https://api.kucoin.com",
        session: Optional[ClientSession] = None,
        json_encoder: JSONEncoder = json.dumps,
        json_decoder: JSONDecoder = json.loads
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase

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
        data: Optional[Union[Dict[str, Any], str]] = None,
        headers: Dict[str, Any] = {},
        method: str = "GET"
    ) -> None:
        if self.api_key is None:
            raise AuthenticationError("api_key")
        elif self.secret is None:
            raise AuthenticationError("secret")
        elif self.passphrase is None:
            raise AuthenticationError("passphrase")

        body = ""
        if method in ("GET", "DELETE"):
            if params is not None and len(params) != 0:
                path += "?" + urlencode(params)
                params.clear()
        else:
            if data is not None and len(data) != 0:
                body = data = self._json_encoder(data)

        timestamp = str(current_timestamp())

        headers["KC-API-KEY"] = self.api_key
        headers["KC-API-SIGN"] = hmac_signature(
            key=self.secret,
            msg=timestamp + method + path + body,
            digest="base64"
        )
        headers["KC-API-PASSPHRASE"] = hmac_signature(
            key=self.secret,
            msg=self.passphrase,
            digest="base64"
        )
        headers["KC-API-TIMESTAMP"] = timestamp
        headers["KC-API-KEY-VERSION"] = "2"

    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        if isinstance(json_data, dict):
            code = json_data.get("code")
            if code != "200000":
                msg = json_data.get("msg")
                if msg is not None:
                    raise ExchangeApiError(code, msg)
