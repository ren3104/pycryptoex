from __future__ import annotations

from aiohttp import ClientSession, WSMsgType

import abc
import asyncio
import logging
from inspect import isawaitable
from typing import TYPE_CHECKING

from .utils import current_timestamp, to_json, from_json
from .exceptions import ExchangeWebsocketError, ExchangeWebsocketClosed

if TYPE_CHECKING:
    from aiohttp import ClientWebSocketResponse

    from collections.abc import Callable
    from typing import Any

logger = logging.getLogger(__name__)


class BaseWebsocket(metaclass=abc.ABCMeta):
    __slots__ = (
        "_connection",
        "_lock",
        "_on_message_callback",
        "_on_open_callback",
        "_on_close_callback",
        "_on_error_callback",
        "private",
        "ping_interval",
        "pong_timeout",
        "_last_pong",
        "_keepalive_loop_task",
        "_receive_loop_task",
        "_listeners",
        "_error",
    )

    def __init__(
        self,
        on_message: Callable[[BaseWebsocket, Any], Any] | None = None,
        on_open: Callable[[BaseWebsocket], Any] | None = None,
        on_close: Callable[[BaseWebsocket, int], Any] | None = None,
        on_error: Callable[[BaseWebsocket, BaseException], Any] | None = None,
        private: bool | None = None,
        ping_interval: float | None = None,
        pong_timeout: float | None = None,
    ) -> None:
        self._connection: ClientWebSocketResponse | None = None
        self._lock = asyncio.Lock()
        self._on_message_callback = on_message
        self._on_open_callback = on_open
        self._on_close_callback = on_close
        self._on_error_callback = on_error

        if private is None:
            self.private = False
        else:
            self.private = private

        if ping_interval is None:
            self.ping_interval = 10.0
        else:
            self.ping_interval = ping_interval

        if pong_timeout is None:
            self.pong_timeout = self.ping_interval * 2
        else:
            self.pong_timeout = pong_timeout

        self._last_pong: int = current_timestamp()
        self._keepalive_loop_task: asyncio.Task[None] | None = None

        self._receive_loop_task: asyncio.Task[None] | None = None
        self._listeners: dict[str, asyncio.Future[Any]] = {}

        self._error: BaseException | None = None

    @property
    def closed(self) -> bool:
        return self._connection is None or self._connection.closed

    async def connect(self, session: ClientSession, url: str) -> None:
        try:
            async with self._lock:
                if self._connection is not None:
                    return

                await self._connect(session, url)
        except BaseException:
            await self.close()
            raise

        if not self.closed:
            await self._callback(self._on_open_callback, self)

    async def _connect(self, session: ClientSession, url: str) -> None:
        self._connection = await session.ws_connect(
            url, autoclose=False, autoping=False
        )

        self._receive_loop_task = asyncio.create_task(self._receive_loop())

        if self.ping_interval > 0:
            self._keepalive_loop_task = asyncio.create_task(
                self._keepalive_loop()
            )

    async def close(self, code: int = 1000) -> None:
        async with self._lock:
            if self._connection is not None and not self._connection.closed:
                await self._connection.close(code=code)

    async def send(self, data: str | Any) -> None:
        if self._connection is None or self._connection.closed:
            raise ExchangeWebsocketClosed()

        if not isinstance(data, str):
            data = to_json(data)

        await self._connection.send_str(data)

    async def request(
        self,
        request_id: str,
        data: Any,
        timeout: float = 10,
    ) -> Any:
        if request_id in self._listeners:
            raise ExchangeWebsocketError(
                f"Request id is already in flight: {request_id!r}"
            )

        future = asyncio.get_running_loop().create_future()
        self._listeners[request_id] = future

        try:
            await self.send(data)

            return await asyncio.wait_for(future, timeout)
        finally:
            self._listeners.pop(request_id, None)

    async def _emit_message(self, data: Any) -> None:
        await self._callback(self._on_message_callback, self, data)

    async def _receive_loop(self) -> None:
        code = 1000
        try:
            while not (self._connection is None or self._connection.closed):
                message = await self._connection.receive()

                if message.type == WSMsgType.TEXT:
                    await self._on_receive_data(from_json(message.data))
                elif message.type == WSMsgType.PONG:
                    self._last_pong = current_timestamp()
                elif message.type == WSMsgType.PING:
                    await self._connection.pong(message.data)
                elif message.type == WSMsgType.CLOSE:
                    code = message.data if isinstance(message.data, int) else 1006
                    break
                elif message.type == WSMsgType.CLOSING:
                    # close by client
                    break
                elif message.type == WSMsgType.CLOSED:
                    # no close frame, the connection is simply gone
                    code = 1006
                    break
                elif message.type == WSMsgType.ERROR:
                    raise ExchangeWebsocketError(
                        f"Websocket transport error: {self._connection.exception()!r}"
                    )
                else:
                    raise ExchangeWebsocketError(
                        f"Unexpected frame type: {message.type!r}"
                    )
        except Exception as e:
            self._set_error(e)
            code = 1006
        finally:
            await self._teardown(code)

    async def _teardown(self, code: int) -> None:
        if self._keepalive_loop_task is not None:
            self._keepalive_loop_task.cancel()

        for request_id in list(self._listeners):
            self._set_listener_result(request_id, ExchangeWebsocketClosed())

        if self._connection is not None and not self._connection.closed:
            await self._connection.close()

        self._connection = None

        if self._error is not None:
            code = 1006
            await self._callback(self._on_error_callback, self, self._error)

        await self._callback(self._on_close_callback, self, code)

    async def _ping(self) -> None:
        # If you change this function, then don't forget
        # to change the handling of self._last_pong
        await self._connection.ping() # type: ignore[union-attr]

    async def _keepalive_loop(self) -> None:
        try:
            while not (self._connection is None or self._connection.closed):
                await asyncio.sleep(self.ping_interval)

                if self._last_pong + self.pong_timeout * 1000 < current_timestamp():
                    raise ExchangeWebsocketError("Timeout for receive pong")

                await self._ping()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._set_error(e)

            if self._connection is not None and not self._connection.closed:
                await self._connection.close(code=1006)

    def _set_listener_result(self, request_id: str, result: Any) -> bool:
        try:
            future = self._listeners.pop(request_id)
            if isinstance(result, BaseException):
                future.set_exception(result)
            else:
                future.set_result(result)
            return True
        except (KeyError, asyncio.InvalidStateError):
            return False

    def _set_error(self, error: BaseException) -> None:
        if self._error is None:
            self._error = error

    async def _callback(self, callback: Callable[..., Any] | None, *args: Any) -> None:
        if callback is None:
            return

        try:
            result = callback(*args)
            if isawaitable(result):
                await result
        except Exception as e:
            if (
                callback is self._on_error_callback
                or callback is self._on_close_callback
            ):
                logger.exception(
                    "Unhandled exception in websocket callback %r", callback)
                return

            self._set_error(e)
            await self.close(1006)

    @abc.abstractmethod
    async def _on_receive_data(self, data: Any) -> None: ...

    @abc.abstractmethod
    async def subscribe(self, topic: str) -> Any: ...

    @abc.abstractmethod
    async def unsubscribe(self, topic: str) -> Any: ...

    @abc.abstractmethod
    def parse_order_update(self, data: dict[str, Any]) -> dict[str, Any]:
        ...
