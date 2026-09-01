class PycryptoexError(Exception):
    """Base class for every exception raised by pycryptoex."""


class AuthenticationError(PycryptoexError):
    def __init__(self) -> None:
        super().__init__("Client requires credentials for a signed request")


class ExchangeApiError(PycryptoexError):
    def __init__(self, code: str, msg: str) -> None:
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.msg = msg


class InvalidNonce(ExchangeApiError): ...


class ExchangeWebsocketError(PycryptoexError): ...


class ExchangeWebsocketClosed(ExchangeWebsocketError): ...
