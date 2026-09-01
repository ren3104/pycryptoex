# PyCryptoEx
<p align="center">
  <a href="https://github.com/ren3104/pycryptoex/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ren3104/pycryptoex" alt="GitHub license"></a>
  <a href="https://pypi.org/project/pycryptoex"><img src="https://img.shields.io/pypi/v/pycryptoex?color=blue" alt="PyPi package version"></a>
  <a href="https://pypi.org/project/pycryptoex"><img src="https://img.shields.io/pypi/pyversions/pycryptoex.svg" alt="Supported python versions"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="linting - Ruff"></a>
  <a href="https://github.com/python/mypy"><img src="https://img.shields.io/badge/types-Mypy-blue.svg" alt="types - Mypy"></a>
</p>

> [!CAUTION]
> This project is currently in alpha version and may have critical changes

A Python library providing a clients for interacting with various APIs of cryptocurrency exchanges for trading and accessing market data.

## Installation
```shell
pip install -U pycryptoex
```

## Quick Start
```python
import asyncio

from pycryptoex.kucoin import KuCoin


async def main():
    async with KuCoin() as kucoin:
        # Request to public endpoints
        tickers = await kucoin.request("/api/v1/market/allTickers")
        print(tickers)


asyncio.run(main())
```

### Private endpoints
```python
from pycryptoex.kucoin import KuCoin


async def main():
    kucoin = KuCoin(
        api_key="YOUR_API_KEY",
        secret="YOUR_API_SECRET",
        passphrase="YOUR_API_PASSPHRASE",
    )
    async with kucoin:
        accounts = await kucoin.request("/api/v1/accounts", signed=True)
        print(accounts)
```

### Websockets
`websocket_connect` returns a connected websocket driven by four optional callbacks.
Each callback may be either a regular function or a coroutine function. The websocket
borrows the client's HTTP session, so it has to be used inside the `async with` block.

```python
import asyncio

from pycryptoex import BaseWebsocket
from pycryptoex.kucoin import KuCoin


async def on_open(ws: BaseWebsocket) -> None:
    print("connected")


async def on_message(ws: BaseWebsocket, message) -> None:
    print(message)


async def on_error(ws: BaseWebsocket, error: BaseException) -> None:
    print("error:", error)


async def on_close(ws: BaseWebsocket, code: int) -> None:
    print("closed with code", code)


async def main():
    async with KuCoin() as kucoin:
        ws = await kucoin.websocket_connect(
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        topic = "/market/candles:BTC-USDT_1min"
        await ws.subscribe(topic)
        await asyncio.sleep(60)
        await ws.unsubscribe(topic)

        await ws.close()


asyncio.run(main())
```

## Development
```shell
hatch run types:check # mypy --strict
hatch fmt --check # ruff format + ruff check
hatch fmt # autofix
```
