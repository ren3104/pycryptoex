from __future__ import annotations

from aiohttp import ClientSession, WSMsgType

import abc
import asyncio
import itertools
from typing import TYPE_CHECKING

from .exceptions import WebsocketClosedError
from .utils import current_timestamp, to_json, from_json

if TYPE_CHECKING:
    from aiohttp import ClientWebSocketResponse

    from typing import Any, Optional, Union, List, Dict, Callable

    Callback = Callable[[Any], Any]


DEFAULT_PING_INTERVAL = 30
DEFAULT_PING_TIMEOUT = 10


class ReconnectingWebsocket:
    __slots__ = (
        "url",
        "_callbacks",
        "_on_start_callback",
        "_on_close_callback",
        "_on_error_callback",
        "_is_own_session",
        "_session",
        "_connection",
        "_receive_loop_task",
        "ping_interval",
        "ping_timeout",
        "_ping_loop_task",
        "_last_pong"
    )

    def __init__(
        self,
        url: str,
        callbacks: Union[Callback, List[Callback]],
        on_start_callback: Optional[Any] = None,
        on_close_callback: Optional[Any] = None,
        on_error_callback: Optional[Any] = None,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        ping_timeout: int = DEFAULT_PING_TIMEOUT,
        session: Optional[ClientSession] = None
    ) -> None:
        self.url = url

        if callable(callbacks):
            callbacks = [callbacks]
        self._callbacks = callbacks

        self._on_start_callback = on_start_callback
        self._on_close_callback = on_close_callback
        self._on_error_callback = on_error_callback

        self._is_own_session = False
        if session is None:
            self._is_own_session = True
            session = ClientSession(
                json_serialize=to_json
            )
        self._session = session

        self._connection: Optional[ClientWebSocketResponse] = None
        self._receive_loop_task: Optional[asyncio.Task] = None

        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._ping_loop_task: Optional[asyncio.Task] = None
        self._last_pong: Optional[int] = None

    @property
    def closed(self) -> bool:
        return (
            self._connection is None or
            self._connection.closed
        )

    async def start(self) -> None:
        if not self.closed:
            return

        try:
            self._connection = await self._session._ws_connect(
                url=self.url,
                autoclose=False,
                autoping=False
            )

            self._ping_loop_task = asyncio.ensure_future(self._ping_loop())
            self._receive_loop_task = asyncio.ensure_future(self._receive_loop())

            if self._on_start_callback is not None:
                await self._on_start_callback(self)
        except Exception as e:
            await self._on_error(e)
            raise

    async def close(self, code: int = 1000) -> None:
        if not self.closed:
            await self._connection.close(code=code)
        
        if self._ping_loop_task is not None:
            self._ping_loop_task.cancel()
        
        if self._receive_loop_task is not None:
            self._receive_loop_task.cancel()

        if self._is_own_session and not self._session.closed:
            await self._session.close()

            # Wait 250 ms for the underlying SSL connections to close
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0.25)
    
    async def _on_close(self, code):
        if self._on_close_callback is not None:
            await self._on_close_callback(self, code)
        await self.close(code)
    
    async def _on_error(self, error):
        if self._on_error_callback is not None:
            await self._on_error_callback(self, error)
        await self.close(1006)

    async def ping(self) -> None:
        # If you change this function, then don't forget
        # to change the handling of self._last_pong
        await self._connection.ping()
    
    async def _ping_loop(self) -> None:
        while not self.closed:
            if (
                self._last_pong is not None and
                self._last_pong + self.ping_timeout < current_timestamp()
            ):
                await self._on_error(TimeoutError(
                    f"Connection to {self.url} timed out due to a ping-pong keepalive missing on time"
                ))
            else:
                try:
                    await self.ping()
                except Exception as e:
                    await self._on_error(e)
            await asyncio.sleep(self.ping_interval)

    def _handle_callback_exception(self, task: asyncio.Task) -> None:
        if not task.cancelled():
            exception = task.exception()
            if exception is not None:
                asyncio.ensure_future(self._on_error(exception))

    async def _receive_loop(self) -> None:
        while not self.closed:
            message = await self._connection.receive()
            if message.type == WSMsgType.TEXT:
                json_data = from_json(message.data)

                for callback in self._callbacks:
                    task = asyncio.create_task(callback(json_data))
                    task.add_done_callback(self._handle_callback_exception)
            elif message.type == WSMsgType.PONG:
                self._last_pong = current_timestamp()
            elif message.type == WSMsgType.CLOSE:
                await self._on_close(message.data)
            elif message.type == WSMsgType.CLOSED:
                await self._on_close(1000)
            elif message.type == WSMsgType.ERROR:
                await self._on_error(Exception(message))


class CommunicatingWebsocket(ReconnectingWebsocket, metaclass=abc.ABCMeta):
    __slots__ = (
        "_counter",
        "_listeners"
    )

    def __init__(
        self,
        url: str,
        callbacks: Optional[Union[Callback, List[Callback]]] = None,
        on_start_callback: Optional[Any] = None,
        on_close_callback: Optional[Any] = None,
        on_error_callback: Optional[Any] = None,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        ping_timeout: int = DEFAULT_PING_TIMEOUT,
        session: Optional[ClientSession] = None
    ) -> None:
        self._counter = itertools.count(0, 1).__next__
        self._listeners: Dict[str, asyncio.Future] = {}
        
        if callbacks is None:
            callbacks = self._handler
        else:
            if callable(callbacks):
                callbacks = [callbacks]

            callbacks.insert(0, self._handler)

        super().__init__(
            url=url,
            callbacks=callbacks,
            on_start_callback=on_start_callback,
            on_close_callback=on_close_callback,
            on_error_callback=on_error_callback,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            session=session
        )

    @abc.abstractmethod
    async def _handler(self, json_data: Any) -> None:
        ...

    def get_new_id(self) -> str:
        return str(self._counter())
    
    def _pop_listener_future(self, id_: str) -> Optional[asyncio.Future]:
        try:
            return self._listeners.pop(id_)
        except KeyError:
            pass
    
    def _set_listener_result(self, id_: str, data: Any) -> bool:
        future = self._pop_listener_future(id_)
        if future is not None and not future.done():
            future.set_result(data)
            return True
        return False

    def _set_listener_error(self, id_: str, error: Exception) -> bool:
        future = self._pop_listener_future(id_)
        if future is not None and not future.done():
            future.set_exception(error)
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
    __slots__ = ("_subscribed_topics")

    def __init__(
        self,
        url: str,
        callbacks: Optional[Union[Callback, List[Callback]]] = None,
        on_start_callback: Optional[Any] = None,
        on_close_callback: Optional[Any] = None,
        on_error_callback: Optional[Any] = None,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        ping_timeout: int = DEFAULT_PING_TIMEOUT,
        session: Optional[ClientSession] = None
    ) -> None:
        self._subscribed_topics: Dict[str, List[Callback]] = {}

        super().__init__(
            url=url,
            callbacks=callbacks,
            on_start_callback=on_start_callback,
            on_close_callback=on_close_callback,
            on_error_callback=on_error_callback,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            session=session
        )
    
    @property
    def subscriptions(self) -> List[str]:
        return list(self._subscribed_topics.keys())
    
    @abc.abstractmethod
    async def _subscribe(self, topic: str) -> None:
        ...
    
    @abc.abstractmethod
    async def _unsubscribe(self, topic: str) -> None:
        ...
    
    async def subscribe(self, topic: str) -> None:
        if topic in self._subscribed_topics:
            return
        
        await self._subscribe(topic)
        
        self._subscribed_topics[topic] = []
    
    async def subscribe_callback(
        self,
        topic: str,
        callbacks: Union[Callback, List[Callback]]
    ) -> None:
        await self.subscribe(topic)

        if callable(callbacks):
            self._subscribed_topics[topic].append(callbacks)
        else:
            self._subscribed_topics[topic].extend(callbacks)
    
    async def unsubscribe(self, topic: str) -> None:
        if topic not in self._subscribed_topics:
            return

        await self._unsubscribe(topic)
    
        del self._subscribed_topics[topic]
    
    async def unsubscribe_callback(
        self,
        topic: str,
        callbacks: Union[Callback, List[Callback]]
    ) -> None:
        if topic not in self._subscribed_topics:
            return
        
        subscribed_topic = self._subscribed_topics[topic]
        
        if callable(callbacks):
            callbacks = [callbacks]
        
        for callback in callbacks:
            try:
                subscribed_topic.remove(callback)
            except ValueError:
                pass
        
        if len(subscribed_topic) == 0:
            await self.unsubscribe(topic)

