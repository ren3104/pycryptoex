from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pycryptoex.base.exchange import BaseExchange
from pycryptoex.base.exceptions import AuthenticationError
from pycryptoex.base.utils import current_timestamp, hmac_signature

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from aiohttp.typedefs import JSONEncoder, JSONDecoder

    from typing import Any, Dict, Optional


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
        headers: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> None:
        if self.api_key is None:
            raise AuthenticationError("api_key")
        elif self.secret is None:
            raise AuthenticationError("secret")
        elif self.passphrase is None:
            raise AuthenticationError("passphrase")

        if params is None:
            params = {}
        if headers is None:
            headers = {}

        timestamp = str(current_timestamp())

        headers["KC-API-KEY"] = self.api_key
        headers["KC-API-SIGN"] = hmac_signature(
            key=self.secret,
            msg=timestamp + method + path + self._json_encoder(params),
            digest="base64"
        )
        headers["KC-API-PASSPHRASE"] = hmac_signature(
            key=self.secret,
            msg=self.passphrase,
            digest="base64"
        )
        headers["KC-API-TIMESTAMP"] = timestamp
        headers["KC-API-KEY-VERSION"] = "2"
