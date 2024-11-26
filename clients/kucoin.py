from __future__ import annotations

import asyncio
from urllib.parse import urlencode
from typing import TYPE_CHECKING

from pycryptoex.base.exchange import BaseExchange
from pycryptoex.base.websocket import BaseStreamManager
from pycryptoex.base.exceptions import (
    AuthenticationError,
    ExchangeApiError,
    ExchangeWebsocketError
)
from pycryptoex.base.utils import to_json, current_timestamp, hmac_signature

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from typing import Any, Optional

    from pycryptoex.base.websocket import ReconnectingWebsocket


class KuCoin(BaseExchange):
    DEFAULT_URL = "https://api.kucoin.com"

    def _sign(
        self,
        path: str,
        params: Optional[dict[str, Any]],
        data: Optional[dict[str, Any]],
        headers: dict[str, Any],
        method: str
    ) -> tuple[Any, ...]:
        if (
            self.api_key is None
            or self.secret is None
            or self.passphrase is None
        ):
            raise AuthenticationError

        data_string: Optional[str] = None
        if params:
            path += "?" + urlencode(params)
            params.clear()
        elif data:
            data_string = to_json(data)

        timestamp = str(current_timestamp())

        headers["KC-API-KEY"] = self.api_key
        headers["KC-API-SIGN"] = hmac_signature(
            key=self.secret,
            msg=timestamp + method + path + (data_string or ""),
            digest="base64"
        )
        headers["KC-API-PASSPHRASE"] = hmac_signature(
            key=self.secret,
            msg=self.passphrase,
            digest="base64"
        )
        headers["KC-API-TIMESTAMP"] = timestamp
        headers["KC-API-KEY-VERSION"] = "2"

        return path, params, data_string, headers, method

    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        if isinstance(json_data, dict):
            code = json_data.get("code")
            if code != "200000":
                msg = json_data.get("msg")
                if msg is not None:
                    raise ExchangeApiError(code, msg)

    async def create_websocket_stream(self, private: bool = False) -> KuCoinStreamManager:
        async def _get_conn_info() -> tuple[str, int]:
            if private:
                token_data = await self.request("/api/v1/bullet-private", method="POST", signed=True)
            else:
                token_data = await self.request("/api/v1/bullet-public", method="POST")

            ws_server_info = token_data["data"]["instanceServers"][0]

            return (
                f"{ws_server_info['endpoint']}?token={token_data['data']['token']}",
                ws_server_info["pingInterval"] // 1000
            )

        async def _on_reconnect(ws: ReconnectingWebsocket) -> None:
            ws._url, ws._keepalive = await _get_conn_info()

        url, keepalive = await _get_conn_info()

        return KuCoinStreamManager(
            url=url,
            keepalive=keepalive,
            on_reconnect_callback=_on_reconnect
        )


class KuCoinStreamManager(BaseStreamManager):
    async def ping(self) -> None:
        await self.send_json({
            self.DEFAULT_ID_KEY: self.get_new_id(),
            "type": "ping"
        })

    async def _on_message(self, data: Any) -> None:
        try:
            type_ = data["type"]
        except KeyError:
            pass
        else:
            if type_ == "message":
                try:
                    handlers = self._subscribed_topic_handlers[data["topic"]]
                except KeyError:
                    pass
                else:
                    for callback in handlers:
                        task = asyncio.create_task(callback(data))
                        task.add_done_callback(self._handle_task_exception)
            elif type_ == "pong":
                self._last_pong = current_timestamp()
            elif type_ == "ack":
                self._set_listener_result(data["id"], data)
            elif type_ == "error":
                err = ExchangeWebsocketError(data["code"], data["data"])
                if not self._set_listener_result(data["id"], err):
                    asyncio.ensure_future(self._on_error(err))

        await super()._on_message(data)

    async def _subscribe(self, topic: str, **params: Any) -> None:
        await self.send_and_recv({
            "type": "subscribe",
            "topic": topic,
            "response": True,
            "privateChannel": params.get("private", False)
        })

    async def _unsubscribe(self, topic: str, **params: Any) -> None:
        await self.send_and_recv({
            "type": "unsubscribe",
            "topic": topic,
            "response": True,
            "privateChannel": params.get("private", False)
        })
