from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from .base.exchange import BaseExchange
from .base.websocket import BaseWebsocket
from .base.utils import to_json, current_timestamp, hmac_base64
from .base.exceptions import (
    PycryptoexError,
    AuthenticationError,
    ExchangeApiError,
    InvalidNonce,
    ExchangeWebsocketError,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


class KuCoin(BaseExchange):
    __slots__ = ()

    DEFAULT_URL = "https://api.kucoin.com"

    def _sign(
        self,
        path: str,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
        headers: dict[str, Any],
        method: str,
    ) -> None:
        if self.api_key is None or self.secret is None or self.passphrase is None:
            raise AuthenticationError()

        body = ""
        if params:
            body = "?" + urlencode(params)
        elif data:
            body = to_json(data)

        timestamp = str(current_timestamp() + (self.timestamp_offset or 0))

        headers["KC-API-SIGN"] = hmac_base64(
            key=self.secret, msg=timestamp + method + path + body
        )
        headers["KC-API-TIMESTAMP"] = timestamp
        if "KC-API-KEY" not in headers:
            headers["KC-API-KEY"] = self.api_key
            headers["KC-API-PASSPHRASE"] = hmac_base64(
                key=self.secret, msg=self.passphrase
            )
            headers["KC-API-KEY-VERSION"] = "2"

    def _handle_errors(self, data: Any) -> None:
        if not isinstance(data, dict):
            return

        code = data.get("code")
        if code == "200000":
            return

        msg = data.get("msg")
        if not isinstance(code, str) or not isinstance(msg, str):
            return

        if code == "400002":
            raise InvalidNonce(code, msg)

        raise ExchangeApiError(code, msg)

    async def get_server_time(self) -> int:
        data: int = (await self.request("/api/v1/timestamp"))["data"]
        return data

    async def websocket_connect(
        self,
        on_message: Callable[[BaseWebsocket, Any], Any] | None = None,
        on_open: Callable[[BaseWebsocket], Any] | None = None,
        on_close: Callable[[BaseWebsocket, int], Any] | None = None,
        on_error: Callable[[BaseWebsocket, BaseException], Any] | None = None,
        private: bool = False,
        url: str | None = None,
    ) -> KuCoinWebsocket:
        if self._session is None:
            raise PycryptoexError("Exchange client is not initialized")

        if private:
            token_data = await self.request(
                "/api/v1/bullet-private", method="POST", signed=True
            )
        else:
            token_data = await self.request("/api/v1/bullet-public", method="POST")

        ws_info = token_data["data"]["instanceServers"][0]
        if url is None:
            url = ws_info["endpoint"]
        url = "{endpoint}?token={token}".format(
            endpoint=url, token=token_data["data"]["token"]
        )
        ping_interval = ws_info["pingInterval"] / 1000

        return await KuCoinWebsocket.connect(
            self._session,
            url,
            private=private,
            on_message=on_message,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error,
            ping_interval=ping_interval,
        )


class KuCoinWebsocket(BaseWebsocket):
    __slots__ = ()

    async def _ping(self) -> None:
        await self.send('{"id":"0","type":"ping"}')

    async def _on_receive_data(self, data: Any) -> None:
        try:
            data_type = data["type"]
        except KeyError:
            return

        if data_type == "message":
            await self._emit_message(data)
        elif data_type == "pong":
            self._last_pong = current_timestamp()
        elif data_type == "ack":
            self._set_listener_result(data["id"], data)
        elif data_type == "error":
            err = ExchangeWebsocketError(data["code"], data["data"])
            if not self._set_listener_result(data["id"], err):
                self._set_error(err)
                await self.close(1006)

    async def subscribe(self, topic: str) -> Any:
        return await self.request(
            request_id=str(uuid.uuid4()),
            data={
                "type": "subscribe",
                "topic": topic,
                "privateChannel": self.private,
                "response": True,
            },
        )

    async def unsubscribe(self, topic: str) -> Any:
        return await self.request(
            request_id=str(uuid.uuid4()),
            data={
                "type": "unsubscribe",
                "topic": topic,
                "privateChannel": self.private,
                "response": True,
            },
        )
