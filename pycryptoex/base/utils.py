from __future__ import annotations

import time
import hmac
import hashlib
from base64 import b64encode
import json
from decimal import Decimal, ROUND_HALF_EVEN
from typing import TYPE_CHECKING

try:
    import orjson

    HAS_ORJSON = True
except ModuleNotFoundError:
    HAS_ORJSON = False

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, ed25519

    HAS_CRYPTO = True
except ModuleNotFoundError:
    HAS_CRYPTO = False

if TYPE_CHECKING:
    from numbers import Number
    from typing import Any


def current_timestamp() -> int:
    return int(time.time() * 1000)


def number_to_precision(
    number: Number,
    precision: str,
    rounding_mode: str = ROUND_HALF_EVEN
) -> str:
    decimal_number = number if isinstance(number, Decimal) else Decimal(str(number))
    return str(decimal_number.quantize(
        Decimal(precision),
        rounding_mode
    ).normalize())


if HAS_ORJSON:

    def to_json(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")

    def from_json(data: str | bytes) -> Any:
        return orjson.loads(data)
else:

    def to_json(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"))

    def from_json(data: str | bytes) -> Any:
        return json.loads(data)


def hmac_digest(key: str, msg: str) -> bytes:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()


def hmac_hex(key: str, msg: str) -> str:
    return hmac.new(
        key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def hmac_base64(key: str, msg: str) -> str:
    return b64encode(hmac_digest(key, msg)).decode("utf-8")


if HAS_CRYPTO:

    def rsa_signature(key: Any, msg: str) -> str:
        if not isinstance(key, rsa.RSAPrivateKey):
            raise TypeError(f"expected RSAPrivateKey, got {type(key).__name__}")
        return b64encode(
            key.sign(msg.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        ).decode("utf-8")

    def eddsa_signature(key: Any, msg: str) -> str:
        if not isinstance(key, ed25519.Ed25519PrivateKey):
            raise TypeError(f"expected Ed25519PrivateKey, got {type(key).__name__}")
        return b64encode(key.sign(msg.encode("utf-8"))).decode("utf-8")
else:

    def rsa_signature(key: Any, msg: str) -> str:
        raise RuntimeError("module named 'cryptography' not found")

    def eddsa_signature(key: Any, msg: str) -> str:
        raise RuntimeError("module named 'cryptography' not found")
