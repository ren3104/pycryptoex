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
    from aiohttp import ClientSession, ClientResponse

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
        session: Optional[ClientSession] = None
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase

        super().__init__(
            url=url,
            session=session
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
                body = data = to_json(data)

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

    async def create_websocket_stream(self, private: bool = False) -> KuCoinStreamManager:
        if private:
            token_data = await self.request("/api/v1/bullet-private", method="POST", signed=True)
        else:
            token_data = await self.request("/api/v1/bullet-public", method="POST")

        ws_server_info = token_data["data"]["instanceServers"][0]

        return KuCoinStreamManager(
            url=f"{ws_server_info['endpoint']}?token={token_data['data']['token']}",
            ping_interval=(ws_server_info["pingInterval"] / 1000),
            ping_timeout=ws_server_info["pingTimeout"] / 1000,
            session=self._session
        )


class KuCoinStreamManager(BaseStreamManager):
    async def ping(self) -> None:
        await self._connection.send_json({
            "id": self.get_new_id(),
            "type": "ping"
        }, dumps=to_json)
    
    async def _handler(self, json_data: Any) -> None:
        try:
            type_ = json_data["type"]
        except KeyError:
            return
        
        if type_ == "message":
            for callback in self._subscribed_topics.get(json_data["topic"]):
                task = asyncio.create_task(callback(json_data))
                task.add_done_callback(self._handle_callback_exception)
        elif type_ == "pong":
            self._last_pong = current_timestamp()
        elif type_ == "ack":
            self._set_listener_result(
                json_data["id"],
                json_data
            )
        elif type_ == "error":
            err = ExchangeWebsocketError(
                json_data["code"],
                json_data["data"]
            )
            if not self._set_listener_error(json_data["id"], err):
                await self._on_error(err)
    
    async def _subscribe(self, topic: str) -> None:
        id_ = self.get_new_id()
        await self.send_and_recv(id_, {
            "id": id_,
            "type": "subscribe",
            "topic": topic,
            "response": True
        })
    
    async def _unsubscribe(self, topic: str) -> None:
        id_ = self.get_new_id()
        await self.send_and_recv(id_, {
            "id": id_,
            "type": "unsubscribe",
            "topic": topic,
            "response": True
        })
