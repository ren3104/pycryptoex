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

Choose and install one or more supported crypto exchanges:
```shell
pycryptoex [names ...]
```

For example:
```shell
pycryptoex bybit kucoin
```

### Install from Github main
```shell
pip install -U git+https://github.com/ren3104/pycryptoex@main
```

```shell
pycryptoex [names ...] --update --version main
```

## Quick Start
```python
import asyncio

from pycryptoex import KuCoin, Bybit


async def handler(json_data):
    print(json_data)


async def main():
    # Request to public endpoints
    kucoin = KuCoin()
    async with kucoin:
        await kucoin.request(...)

    # Request to private endpoints
    bybit = Bybit(
        api_key="YOUR_API_KEY",
        secret="YOUR_API_SECRET"
    )
    async with bybit:
        await bybit.request(..., signed=True)

    # Start the public websocket
    kucoin_public_ws = await kucoin.create_websocket_stream()
    await kucoin_public_ws.start()
    # Subscribe handler to a public channel
    topic = "/market/candles:BTC-USDT_1min"
    await kucoin_public_ws.subscribe_callback(topic, handler)
    # Unsubscribe handler from a public channel
    await kucoin_public_ws.unsubscribe_callback(topic, handler)
    # Unsubscribe all handlers from a public channel
    await kucoin_public_ws.unsubscribe(topic)
    # Stop the public websocket
    await kucoin_public_ws.close()

    # Start the private websocket
    kucoin_private_ws = await kucoin.create_websocket_stream(private=True)
    await kucoin_private_ws.start()
    # Subscribe to private channels
    await kucoin_private_ws.subscribe_callback("/account/balance", handler)

    # Block until websockets close
    while not kucoin_public_ws.closed or not kucoin_private_ws.closed:
        await asyncio.sleep(0.1)
```

## Supported Crypto Exchanges
| Exchange | Api Client | Websocket Stream Manager
| --- | --- | --- |
| [Bybit](https://www.bybit.com/invite?ref=0WXGNA5) | + | - |
| [KuCoin](https://www.kucoin.com/r/rf/QBAAD3Y5) | + | + |
