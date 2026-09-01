from __future__ import annotations

from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ClientConnectionError

try:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    HAS_CRYPTO = True
except ModuleNotFoundError:
    HAS_CRYPTO = False

import abc
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from .websocket import BaseWebsocket
from .exceptions import PycryptoexError, InvalidNonce
from .utils import to_json, from_json, current_timestamp

if TYPE_CHECKING:
    import sys
    from types import TracebackType
    from collections.abc import Callable
    from typing import Any

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self


class BaseExchange(metaclass=abc.ABCMeta):
    __slots__ = (
        "api_key",
        "secret",
        "passphrase",
        "private_key",
        "base_url",
        "_session",
        "timestamp_offset",
    )

    DEFAULT_URL = ""
    DEFAULT_TIMEOUT = ClientTimeout(total=10)
    MAX_RETRIES = 3
    RETRY_WAIT = 3

    def __init__(
        self,
        api_key: str | None = None,
        secret: str | None = None,
        passphrase: str | None = None,
        private_key: str | Path | None = None,
        private_key_pass: str | None = None,
        base_url: str | None = None,
        timestamp_offset: int | None = None,
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase

        self.private_key: Any | None = None
        if private_key is not None:
            if not HAS_CRYPTO:
                raise RuntimeError("Module named 'cryptography' is not installed")

            if isinstance(private_key, Path) or Path(private_key).is_file():
                private_key = Path(private_key).read_text(encoding="utf-8")

            self.private_key = load_pem_private_key(
                data=private_key.encode("utf-8"),
                password=(
                    private_key_pass.encode("utf-8")
                    if private_key_pass is not None
                    else None
                ),
            )

        if base_url is not None:
            self.base_url = base_url
        else:
            self.base_url = self.DEFAULT_URL
        self._session: ClientSession | None = None
        self.timestamp_offset = timestamp_offset

    @property
    def closed(self) -> bool:
        return self._session is None or self._session.closed

    def _create_session(self) -> ClientSession:
        return ClientSession(
            headers={
                "Content-Type": "application/json;charset=utf-8",
                "User-Agent": "pycryptoex",
            },
            json_serialize=to_json,
        )

    @abc.abstractmethod
    def _sign(
        self,
        path: str,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
        headers: dict[str, Any],
        method: str,
    ) -> None: ...

    def _handle_errors(self, data: Any) -> None:
        pass

    async def request(
        self,
        path: str,
        signed: bool = False,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        method: str = "GET",
        max_retries: int | None = None,
        **request_kwargs: Any,
    ) -> Any:
        if max_retries is None:
            max_retries = self.MAX_RETRIES

        if "timeout" not in request_kwargs:
            request_kwargs["timeout"] = self.DEFAULT_TIMEOUT

        for attempt in range(max_retries + 1):
            if self._session is None:
                raise PycryptoexError("Exchange client is not initialized")
            elif self._session.closed:
                self._session = self._create_session()

            if signed:
                if headers is None:
                    headers = {}

                self._sign(path, params, data, headers, method)

            try:
                async with self._session.request(
                    method=method,
                    url=self.base_url + path,
                    params=params,
                    json=data,
                    headers=headers,
                    **request_kwargs,
                ) as response:
                    json_data = await response.json(encoding="utf-8", loads=from_json)

                    self._handle_errors(json_data)

                    response.raise_for_status()

                    return json_data
            except (
                ClientConnectionError,  # Connector is closed
                asyncio.TimeoutError,  # Request timeout
                InvalidNonce,
            ):
                if attempt == max_retries:
                    raise

            await asyncio.sleep(self.RETRY_WAIT)

    @abc.abstractmethod
    async def websocket_connect(
        self,
        on_message: Callable[[BaseWebsocket, Any], Any] | None = None,
        on_open: Callable[[BaseWebsocket], Any] | None = None,
        on_close: Callable[[BaseWebsocket, int], Any] | None = None,
        on_error: Callable[[BaseWebsocket, BaseException], Any] | None = None,
        private: bool = False,
        url: str | None = None,
    ) -> BaseWebsocket: ...

    @abc.abstractmethod
    async def get_server_time(self) -> int: ...

    async def __aenter__(self) -> Self:
        if self.closed:
            self._session = self._create_session()

        if self.timestamp_offset is None:
            self.timestamp_offset = await self.get_server_time() - current_timestamp()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            # Wait 250 ms for the underlying SSL connections to close
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0.25)
