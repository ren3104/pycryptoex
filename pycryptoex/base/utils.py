from __future__ import annotations

import time
import hmac
import hashlib
from base64 import b64encode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Union


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
        return b64encode(hmac_obj.digest())
    return hmac_obj.digest()
