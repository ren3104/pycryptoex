class AuthenticationError(Exception):
    def __init__(self, var_name: str) -> None:
        super().__init__(f"Client requires {var_name} for signed request")


class ExchangeApiError(Exception):
    ...


class WebsocketClosedError(Exception):
    def __init__(self) -> None:
        super().__init__("Websocket connection is closed")


class ExchangeWebsocketError(Exception):
    ...
