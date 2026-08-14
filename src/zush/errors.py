from __future__ import annotations


class ZushError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class IntegrationError(ZushError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=1)
