# PyCryptoEx
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
- [Bybit](https://www.bybit.com)
- [KuCoin](https://www.kucoin.com)
