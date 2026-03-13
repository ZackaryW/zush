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

from zush.persistence import persisted_ctx
from zush.paths import default_storage


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

    __slots__ = ("_commands", "_plugin_name", "_storage")

    def __init__(self) -> None:
        self._commands: dict[str, click.Command | click.Group] = {}
        self._plugin_name: str | None = None
        self._storage = None

    def group(self, name: str, help: str | None = None, **kwargs: Any) -> Section:
        """Add a top-level group and return a Section for it."""
        if name not in self._commands:
            self._commands[name] = click.Group(name, help=help or name, **kwargs)
        return Section(self, (name,))

    @property
    def commands(self) -> dict[str, click.Command | click.Group]:
        """The commands dict (dotted keys). This is what the loader expects on the plugin instance."""
        return self._commands

    def _bind_runtime(self, plugin_name: str, storage: Any | None = None) -> None:
        """Bind runtime metadata needed by helper features such as persistedCtx()."""
        self._plugin_name = plugin_name
        self._storage = storage or default_storage()

    def persistedCtx(self, name: str | None = None):
        """Yield a persisted config object or text buffer for this plugin."""
        if self._plugin_name is None:
            raise RuntimeError("Plugin runtime is not bound; persistedCtx is unavailable")
        storage = self._storage or default_storage()
        return persisted_ctx(self._plugin_name, storage, filename=name)
