from __future__ import annotations

try:
    from Crypto.Hash import SHA256 # type: ignore
    from Crypto.Signature import PKCS1_v1_5, eddsa # type: ignore
    from Crypto.PublicKey import RSA, ECC # type: ignore
except ModuleNotFoundError:
    pass

import time
import hmac
import hashlib
from base64 import b64encode
import json
from typing import TYPE_CHECKING

try:
    import orjson # type: ignore
except ModuleNotFoundError:
    HAS_ORJSON = False
else:
    HAS_ORJSON = True

if TYPE_CHECKING:
    from typing import overload, Any, Union, Literal


def current_timestamp() -> int:
    return int(time.time() * 1000)


if TYPE_CHECKING:
    @overload
    def hmac_signature(key: str, msg: str, digest: Literal["hex", "base64"] = ...) -> str: ...

    @overload
    def hmac_signature(key: str, msg: str, digest: str = ...) -> bytes: ...

def hmac_signature(key: str, msg: str, digest: str = "hex") -> Union[str, bytes]:
    hmac_obj = hmac.new(
        key.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256
    )
    if digest == "hex":
        return hmac_obj.hexdigest()
    elif digest == "base64":
        return b64encode(hmac_obj.digest()).decode("utf-8")
    return hmac_obj.digest()


def rsa_signature(key: RSA.RsaKey, msg: str) -> str:
    hash_ = SHA256.new(msg.encode("utf-8"))
    signature = PKCS1_v1_5.new(key).sign(hash_)
    return b64encode(signature).decode("utf-8")


def eddsa_signature(key: ECC.EccKey, msg: str) -> str:
    signature = eddsa.new(key, "rfc8032").sign(msg.encode("utf-8"))
    return b64encode(signature).decode("utf-8")


if HAS_ORJSON:
    def to_json(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")

    from_json = orjson.loads

else:
    def to_json(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"))

    from_json = json.loads
