from __future__ import annotations

import time
import hmac
import hashlib
from base64 import b64encode
import json
from typing import TYPE_CHECKING

try:
    import orjson
except ModuleNotFoundError:
    HAS_ORJSON = False
else:
    HAS_ORJSON = True

if TYPE_CHECKING:
    from typing import Any, Union


def current_timestamp() -> int:
    return int(time.time() * 1000)


def hmac_signature(
    key: str,
    msg: str,
    digest: str = "hex"
) -> Union[str, bytes]:
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


if HAS_ORJSON:

    def to_json(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")

    from_json = orjson.loads

else:

    def to_json(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"))

    from_json = json.loads
