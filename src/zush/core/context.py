"""ZushCtx (observable dict) and hook registry for beforeCmd/afterCmd/onError/onCtxMatch."""

from __future__ import annotations

import re
from typing import Callable, TypeVar, cast

E = TypeVar("E", bound=BaseException)


class ZushCtx(dict):
    """Dict-like context; on set, runs registered onCtxMatch callbacks when ctx[key] == value."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_ctx_match: list[tuple[str, object, Callable[[], None]]] = []

    def register_on_ctx_match(self, key: str, value: object, callback: Callable[[], None]) -> None:
        """When ctx[key] is set and equals value, call callback (equality with ==)."""
        self._on_ctx_match.append((key, value, callback))

    def __setitem__(self, key: str, value: object) -> None:
        super().__setitem__(key, value)
        for registered_key, expected, callback in self._on_ctx_match:
            if registered_key == key and value == expected:
                callback()


class HookRegistry:
    """Stores and runs beforeCmd, afterCmd, onError hooks."""

    def __init__(self) -> None:
        self._before: list[tuple[re.Pattern[str], Callable[[str], None]]] = []
        self._after: list[tuple[re.Pattern[str], Callable[[str], None]]] = []
        self._on_error: list[tuple[type[BaseException], Callable[[BaseException], None]]] = []

    def register_before_cmd(self, pattern: re.Pattern[str], callback: Callable[[str], None]) -> None:
        self._before.append((pattern, callback))

    def register_after_cmd(self, pattern: re.Pattern[str], callback: Callable[[str], None]) -> None:
        self._after.append((pattern, callback))

    def register_on_error(self, exc_type: type[E], callback: Callable[[E], None]) -> None:
        self._on_error.append(
            (cast(type[BaseException], exc_type), cast(Callable[[BaseException], None], callback))
        )

    def run_before_cmd(self, command_path: str) -> None:
        for pattern, callback in self._before:
            if pattern.search(command_path):
                callback(command_path)

    def run_after_cmd(self, command_path: str) -> None:
        for pattern, callback in self._after:
            if pattern.search(command_path):
                callback(command_path)

    def run_on_error(self, exc: BaseException) -> None:
        for exc_type, callback in self._on_error:
            if isinstance(exc, exc_type):
                callback(exc)
