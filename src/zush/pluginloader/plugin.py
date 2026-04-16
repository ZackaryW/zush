"""Helper to build zush plugins with a chainable API."""

from __future__ import annotations

from typing import Any, Callable

import click

from zush.core.persistence import persisted_ctx
from zush.core.runtime import PluginRuntime
from zush.core.services import ServiceDefinition
from zush.core.storage import default_storage


ProviderFactorySpec = dict[str, Any]


class PluginCommand(click.Command):
    """Click command that exposes usage pieces in parent help listings."""

    def get_short_help_str(self, limit: int = 45) -> str:
        ctx = click.Context(self)
        usage = " ".join(self.collect_usage_pieces(ctx)).strip()
        help_text = self.short_help or self.help or ""
        summary = f"{usage} {help_text}".strip() if help_text else usage
        if not summary:
            return ""
        if len(summary) <= limit:
            return summary
        if limit <= 3:
            return "." * max(limit, 0)
        return summary[: limit - 3].rstrip() + "..."


class Section:
    """Represents a group in the tree; use .group() to nest, .command() to add commands."""

    __slots__ = ("_plugin", "_path")

    def __init__(self, plugin: Plugin, path: tuple[str, ...]) -> None:
        self._plugin = plugin
        self._path = path

    def group(self, name: str, help: str | None = None, **kwargs: Any) -> Section:
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
        key = ".".join((*self._path, name))
        self._plugin._commands[key] = PluginCommand(
            name,
            callback=callback,
            help=help or name,
            **kwargs,
        )
        return self


class Plugin:
    """Build a plugin's .commands dict via chainable .group() and .command()."""

    __slots__ = (
        "_commands",
        "_system_commands",
        "_plugin_name",
        "_provided_globals",
        "_provided_factories",
        "_services",
        "_storage",
        "_runtime",
    )

    def __init__(self) -> None:
        self._commands: dict[str, click.Command | click.Group] = {}
        self._system_commands: dict[str, click.Command | click.Group] = {}
        self._plugin_name: str | None = None
        self._provided_globals: dict[str, Any] = {}
        self._provided_factories: dict[str, ProviderFactorySpec] = {}
        self._services: dict[str, ServiceDefinition] = {}
        self._storage = None
        self._runtime: PluginRuntime | None = None

    def group(self, name: str, help: str | None = None, **kwargs: Any) -> Section:
        if name not in self._commands:
            self._commands[name] = click.Group(name, help=help or name, **kwargs)
        return Section(self, (name,))

    @property
    def commands(self) -> dict[str, click.Command | click.Group]:
        """Return the plugin's regular command tree keyed by dotted path."""
        return self._commands

    @property
    def system_commands(self) -> dict[str, click.Command | click.Group]:
        """Return commands that zush may mount directly under the reserved self group."""
        return self._system_commands

    def system_command(
        self,
        name: str,
        callback: Callable[..., Any] | None = None,
        help: str | None = None,
        **kwargs: Any,
    ) -> Plugin:
        """Register one controlled system command for mounting under self."""
        self._system_commands[name] = PluginCommand(
            name,
            callback=callback,
            help=help or name,
            **kwargs,
        )
        return self

    @property
    def provided_globals(self) -> dict[str, Any]:
        return self._provided_globals

    def provide(self, name: str, value: Any) -> Plugin:
        self._provided_globals[name] = value
        return self

    @property
    def provided_factories(self) -> dict[str, ProviderFactorySpec]:
        return self._provided_factories

    def provide_factory(
        self,
        name: str,
        factory: Callable[..., Any],
        service: str | None = None,
        recreate_on_restart: bool = False,
        teardown: Callable[[Any], None] | None = None,
    ) -> Plugin:
        self._provided_factories[name] = {
            "factory": factory,
            "service": service,
            "recreate_on_restart": recreate_on_restart,
            "teardown": teardown,
        }
        return self

    @property
    def services(self) -> dict[str, ServiceDefinition]:
        return self._services

    def service(
        self,
        name: str,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        auto_restart: bool = False,
        healthcheck: Callable[[dict[str, Any]], bool | tuple[bool, str]] | None = None,
        control: Any | None = None,
        terminate_fallback: bool = True,
    ) -> Plugin:
        self._services[name] = ServiceDefinition(
            command=list(command),
            cwd=cwd,
            env=dict(env or {}),
            auto_restart=auto_restart,
            healthcheck=healthcheck,
            control=control,
            terminate_fallback=terminate_fallback,
        )
        return self

    @property
    def runtime(self) -> PluginRuntime:
        if self._runtime is None:
            raise RuntimeError("Plugin runtime is not bound")
        return self._runtime

    def _bind_runtime(
        self,
        plugin_name: str,
        storage: Any | None = None,
        service_controller: Any | None = None,
        owned_services: set[str] | None = None,
    ) -> None:
        self._plugin_name = plugin_name
        self._storage = storage or default_storage()
        self._runtime = PluginRuntime(
            plugin_name,
            self._storage,
            service_controller=service_controller,
            owned_services=owned_services,
        )

    def persistedCtx(self, name: str | None = None):
        if self._plugin_name is None:
            raise RuntimeError("Plugin runtime is not bound; persistedCtx is unavailable")
        storage = self._storage or default_storage()
        return persisted_ctx(self._plugin_name, storage, filename=name)
