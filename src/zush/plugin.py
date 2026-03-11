"""Helper to build zush plugins with a chainable API. Use from __zush__.py:

    from zush.plugin import Plugin

    def greet_cb(): ...
    p = Plugin()
    p.group("demo", help="Demo commands").command("greet", callback=greet_cb, help="Say hello")
    ZushPlugin = p
"""

from __future__ import annotations

from typing import Any, Callable

import click


class Section:
    """Represents a group in the tree; use .group() to nest, .command() to add commands."""

    __slots__ = ("_plugin", "_path")

    def __init__(self, plugin: Plugin, path: tuple[str, ...]) -> None:
        self._plugin = plugin
        self._path = path

    def group(self, name: str, help: str | None = None, **kwargs: Any) -> Section:
        """Add a nested group and return a Section for it (for further .group() / .command())."""
        key = ".".join((*self._path, name))
        if key not in self._plugin._commands:
            self._plugin._commands[key] = click.Group(name, help=help or name, **kwargs)
        return Section(self._plugin, (*self._path, name))

    def command(
        self,
        name: str,
        callback: Callable[..., Any] | None = None,
        help: str | None = None,
        **kwargs: Any,
    ) -> Section:
        """Add a command under this group. Returns self for chaining."""
        key = ".".join((*self._path, name))
        self._plugin._commands[key] = click.Command(
            name, callback=callback, help=help or name, **kwargs
        )
        return self


class Plugin:
    """Build a plugin's .commands dict via chainable .group() and .command()."""

    __slots__ = ("_commands",)

    def __init__(self) -> None:
        self._commands: dict[str, click.Command | click.Group] = {}

    def group(self, name: str, help: str | None = None, **kwargs: Any) -> Section:
        """Add a top-level group and return a Section for it."""
        if name not in self._commands:
            self._commands[name] = click.Group(name, help=help or name, **kwargs)
        return Section(self, (name,))

    @property
    def commands(self) -> dict[str, click.Command | click.Group]:
        """The commands dict (dotted keys). This is what the loader expects on the plugin instance."""
        return self._commands
