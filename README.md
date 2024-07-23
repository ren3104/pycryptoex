# PyCryptoEx
<p align="center">
  <a href="https://github.com/ren3104/pycryptoex/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ren3104/pycryptoex" alt="GitHub license"></a>
  <a href="https://pypi.org/project/pycryptoex"><img src="https://img.shields.io/pypi/v/pycryptoex?color=blue" alt="PyPi package version"></a>
  <a href="https://pypi.org/project/pycryptoex"><img src="https://img.shields.io/pypi/pyversions/pycryptoex.svg" alt="Supported python versions"></a>
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
from pycryptoex import KuCoin, Bybit


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
```

## Supported Crypto Exchanges
| Exchange | Api Client | Websocket Stream Manager
| --- | --- | --- |
| [Bybit](https://www.bybit.com/invite?ref=0WXGNA5) | + | - |
| [KuCoin](https://www.kucoin.com/r/rf/QBAAD3Y5) | + | + |
