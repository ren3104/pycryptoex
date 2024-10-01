from __future__ import annotations

from aiohttp import ClientSession, WSMsgType

import abc
import asyncio
import itertools
from typing import TYPE_CHECKING, cast

from .exceptions import WebsocketClosedError
from .utils import current_timestamp, to_json, from_json

if TYPE_CHECKING:
    from aiohttp import ClientWebSocketResponse

    from collections.abc import Callable, Iterable
    from typing import Any, Optional, Union

    Callback = Callable[[Any], Any]


class ReconnectingWebsocket:
    __slots__ = (
        "_url",
        "_on_message_callback",
        "_on_connected_callback",
        "_on_reconnect_callback",
        "_on_close_callback",
        "_on_error_callback",
        "_keepalive",
        "_ping_loop_task",
        "_last_pong",
        "_auto_reconnect",
        "_reconnection_codes",
        "_session",
        "_connection",
        "_receive_loop_task"
    )
    
    def __init__(
        self,
        url: str,
        on_message_callback: Optional[Any] = None,
        on_connected_callback: Optional[Any] = None,
        on_reconnect_callback: Optional[Any] = None,
        on_close_callback: Optional[Any] = None,
        on_error_callback: Optional[Any] = None,
        keepalive: int = 10,
        auto_reconnect: bool = True,
        reconnection_codes: Iterable[int] = (1000, 1001, 1005)
    ) -> None:
        self._url = url

        self._on_message_callback = on_message_callback
        self._on_connected_callback = on_connected_callback
        self._on_reconnect_callback = on_reconnect_callback
        self._on_close_callback = on_close_callback
        self._on_error_callback = on_error_callback

        self._keepalive = keepalive * 1000
        self._ping_loop_task: Optional[asyncio.Task] = None
        self._last_pong: Optional[int] = None

        self._auto_reconnect = auto_reconnect
        self._reconnection_codes = reconnection_codes

        self._session: Optional[ClientSession] = None
        self._connection: Optional[ClientWebSocketResponse] = None
        self._receive_loop_task: Optional[asyncio.Task] = None

        self._post_init()

    def _post_init(self) -> None:
        pass

    @property
    def closed(self) -> bool:
        return self._connection is None or self._connection.closed

    async def start(self) -> None:
        if not self.closed:
            return
        
        try:
            if self._session is None or self._session.closed:
                self._session = ClientSession()

            self._connection = await self._session._ws_connect(
                url=self._url,
                autoclose=False,
                autoping=False
            )

            if self._on_connected_callback is not None:
                await self._on_connected_callback(self)

            self._ping_loop_task = asyncio.ensure_future(self._ping_loop())
            self._receive_loop_task = asyncio.ensure_future(self._receive_loop())
        except Exception as e:
            await self._on_error(e)

    async def stop(self, code: int = 1000) -> None:
        if not self.closed:
            await self._connection.close(code=code)

        if self._ping_loop_task is not None:
            self._ping_loop_task.cancel()

        if self._receive_loop_task is not None:
            self._receive_loop_task.cancel()
        
        if self._session is not None and not self._session.closed:
            await self._session.close()

            # Wait 250 ms for the underlying SSL connections to close
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0.25)
    
    async def restart(self) -> None:
        if self._on_reconnect_callback is not None:
            await self._on_reconnect_callback(self)

        await self.stop()
        await self.start()

    async def _on_message(self, data: Any) -> None:
        if self._on_message_callback is not None:
            await self._on_message_callback(self, data)

    async def _on_close(self, code: int) -> None:
        if self._auto_reconnect and code in self._reconnection_codes:
            await self.restart()
            return

        if self._on_close_callback is not None:
            await self._on_close_callback(self, code)
        
        await self.stop(code)
    
    async def _on_error(self, error: Exception) -> None:
        if self._on_error_callback is not None:
            await self._on_error_callback(self, error)
        
        await self.stop(1006)
    
    async def _receive_loop(self) -> None:
        while not self.closed:
            message = await self._connection.receive()
            if message.type == WSMsgType.TEXT:
                await self._on_message(from_json(message.data))
            elif message.type == WSMsgType.PONG:
                self._last_pong = current_timestamp()
            else:
                if message.type == WSMsgType.CLOSE:
                    asyncio.ensure_future(self._on_close(cast(int, message.data)))
                elif message.type == WSMsgType.CLOSED:
                    asyncio.ensure_future(self._on_close(1000))
                elif message.type == WSMsgType.ERROR:
                    asyncio.ensure_future(self._on_error(Exception(message)))
                break

    async def ping(self) -> None:
        # If you change this function, then don't forget
        # to change the handling of self._last_pong
        await self._connection.ping()

    async def _ping_loop(self) -> None:
        while not self.closed:
            if (
                self._last_pong is not None and
                self._last_pong + self._keepalive < current_timestamp()
            ):
                asyncio.ensure_future(self.restart())
                break
            else:
                try:
                    await self.ping()
                except Exception as e:
                    await self._on_error(e)
            await asyncio.sleep(self._keepalive / 1000)


class CommunicatingWebsocket(ReconnectingWebsocket, metaclass=abc.ABCMeta):
    __slots__ = (
        "_counter",
        "_listeners"
    )

    def _post_init(self) -> None:
        super()._post_init()
        self._counter = itertools.count(0, 1).__next__
        self._listeners: dict[str, asyncio.Future] = {}

    def get_new_id(self) -> str:
        return str(self._counter())
    
    def _set_listener_result(self, id_: str, result: Any) -> bool:
        future = self._listeners.pop(id_, None)
        if future is not None and not future.done():
            if isinstance(result, BaseException):
                future.set_exception(result)
            else:
                future.set_result(result)
            return True
        return False

    async def send_and_recv(self, id_: str, data: Any) -> Any:
        if self.closed:
            raise WebsocketClosedError()
        
        future = asyncio.get_running_loop().create_future()
        self._listeners[id_] = future

        await self._connection.send_json(data, dumps=to_json)

        return await asyncio.wait_for(future, 10)


class BaseStreamManager(CommunicatingWebsocket, metaclass=abc.ABCMeta):
    __slots__ = (
        "_subscribed_topic_handlers",
        "_subscribed_topic_params"
    )

    def _post_init(self) -> None:
        super()._post_init()
        self._subscribed_topic_handlers: dict[str, list[Callback]] = {}
        self._subscribed_topic_params: dict[str, dict[str, Any]] = {}
    
    @property
    def subscriptions(self) -> list[str]:
        return list(self._subscribed_topic_handlers.keys())
    
    @abc.abstractmethod
    async def _subscribe(self, topic: str, **params: Any) -> None:
        ...
    
    @abc.abstractmethod
    async def _unsubscribe(self, topic: str, **params: Any) -> None:
        ...
    
    async def subscribe(self, topic: str, **params: Any) -> None:
        if topic in self._subscribed_topic_handlers:
            return
        
        await self._subscribe(topic, **params)
        
        if len(params) > 0:
            self._subscribed_topic_params[topic] = params
        self._subscribed_topic_handlers[topic] = []
    
    async def subscribe_callback(
        self,
        topic: str,
        callbacks: Union[Callback, list[Callback]],
        **params: Any
    ) -> None:
        await self.subscribe(topic, **params)

        if callable(callbacks):
            self._subscribed_topic_handlers[topic].append(callbacks)
        else:
            self._subscribed_topic_handlers[topic].extend(callbacks)
    
    async def unsubscribe(self, topic: str, **params: Any) -> None:
        if topic not in self._subscribed_topic_handlers:
            return

        await self._unsubscribe(topic, **params)
    
        try:
            del self._subscribed_topic_handlers[topic]
            del self._subscribed_topic_params[topic]
        except KeyError:
            pass
    
    async def unsubscribe_callback(
        self,
        topic: str,
        callbacks: Union[Callback, list[Callback]],
        **params: Any
    ) -> None:
        if topic not in self._subscribed_topic_handlers:
            return
        
        subscribed_topic = self._subscribed_topic_handlers[topic]
        
        if callable(callbacks):
            callbacks = [callbacks]
        
        for callback in callbacks:
            try:
                subscribed_topic.remove(callback)
            except ValueError:
                pass
        
        if len(subscribed_topic) == 0:
            await self.unsubscribe(topic, **params)
    
    async def restart(self) -> None:
        await super().restart()

        for topic in self.subscriptions:
            params = self._subscribed_topic_params.get(topic)
            if params is None:
                await self._subscribe(topic)
            else:
                await self._subscribe(topic, **params)
    
    def _handle_task_exception(self, task: asyncio.Task) -> None:
        if not task.cancelled():
            exception = task.exception()
            if exception is not None:
                asyncio.ensure_future(self._on_error(exception))

