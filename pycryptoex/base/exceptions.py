class AuthenticationError(Exception):
    def __init__(self) -> None:
        super().__init__("Client requires credentials for a signed request")


class ExchangeApiError(Exception):
    ...


class ReconnectWebsocketError(Exception):
    ...


class ExchangeWebsocketError(Exception):
    ...
