from __future__ import annotations

from aiohttp import ClientSession
try:
    from Crypto.PublicKey import RSA, ECC # type: ignore
except ModuleNotFoundError:
    HAS_CRYPTO = False
else:
    HAS_CRYPTO = True

import abc
import asyncio
import sys
from os import path
from pathlib import Path
from typing import TYPE_CHECKING

from ..__version__ import __version__
from .utils import to_json, from_json

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from typing import Any, Optional, Union

    from .websocket import BaseStreamManager


DEFAULT_HEADERS = {
    "Content-Type": "application/json;charset=utf-8",
    "User-Agent": "pycryptoex-" + __version__
}


class BaseExchange(metaclass=abc.ABCMeta):
    __slots__ = (
        "api_key",
        "secret",
        "passphrase",
        "private_key",
        "base_url",
        "_session"
    )

    DEFAULT_URL = ""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        private_key: Optional[Union[str, Path]] = None,
        private_key_pass: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase

        self.private_key: Optional[Any] = None
        if private_key is not None:
            if not HAS_CRYPTO:
                raise RuntimeError("Module named 'pycryptodome' not found")

            if isinstance(private_key, Path) or path.isfile(private_key):
                with open(private_key, "r") as f:
                    private_key = f.read()

            for key_importer in (RSA, ECC):
                try:
                    self.private_key = key_importer.import_key(private_key, private_key_pass)
                except ValueError:
                    pass
                else:
                    break
            else:
                raise ValueError("Private key format is not supported")

        self.base_url = self.DEFAULT_URL if base_url is None else base_url
        self._session: Optional[ClientSession] = None

    @property
    def closed(self) -> bool:
        return self._session is None or self._session.closed

    def _create_session(self) -> None:
        self._session = ClientSession(json_serialize=to_json)

    @abc.abstractmethod
    def _sign(
        self,
        path: str,
        params: Optional[dict[str, Any]],
        data: Optional[dict[str, Any]],
        headers: dict[str, Any],
        method: str
    ) -> tuple[Any, ...]:
        ...

    def _handle_errors(self, response: ClientResponse, json_data: Any) -> None:
        pass

    async def request(
        self,
        path: str,
        signed: bool = False,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        method: str = "GET",
        **request_kwargs: Any
    ) -> Any:
        if self.closed:
            self._create_session()

        if headers is None:
            headers = DEFAULT_HEADERS.copy()
        else:
            headers.update(DEFAULT_HEADERS)

        data_string: Optional[str] = None

        if signed:
            path, params, data_string, headers, method = self._sign(path, params, data, headers, method)

        if data_string is None and data:
            data_string = to_json(data)

        async with self._session.request( # type: ignore [union-attr]
            method=method,
            url=self.base_url + path,
            params=params,
            data=data_string,
            headers=headers,
            **request_kwargs
        ) as response:
            json_data = await response.json(
                encoding="utf-8",
                loads=from_json
            )

            self._handle_errors(response, json_data)

            response.raise_for_status()

            return json_data

    async def create_websocket_stream(self, private: bool = False) -> BaseStreamManager:
        raise NotImplementedError

    async def __aenter__(self) -> Self:
        if self.closed:
            self._create_session()

        return self

    async def __aexit__(self, *args: Any) -> None:
        if not self.closed:
            await self._session.close() # type: ignore [union-attr]

            # Wait 250 ms for the underlying SSL connections to close
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0.25)
