from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING, Any

from zush.core.context import HookRegistry, ZushCtx
from zush.core.runtime import g

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def register_plugin_hooks(
    plugins: list[tuple[Any, Any, Any]],
    hook_registry: HookRegistry,
    zush_ctx: ZushCtx,
) -> None:
    for _path, instance, _commands in plugins:
        before = getattr(instance, "before_cmd", None)
        if before and isinstance(before, list):
            for pattern, callback in before:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                hook_registry.register_before_cmd(pattern, callback)
        after = getattr(instance, "after_cmd", None)
        if after and isinstance(after, list):
            for pattern, callback in after:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                hook_registry.register_after_cmd(pattern, callback)
        on_error = getattr(instance, "on_error", None)
        if on_error and isinstance(on_error, list):
            for exc_type, callback in on_error:
                hook_registry.register_on_error(exc_type, callback)
        on_ctx_match = getattr(instance, "on_ctx_match", None)
        if on_ctx_match and isinstance(on_ctx_match, list):
            for key, value, callback in on_ctx_match:
                zush_ctx.register_on_ctx_match(key, value, callback)


def bind_plugin_runtime(plugins: list[tuple[Any, Any, Any]], storage: ZushStorage) -> None:
    bind_plugin_runtime_with_services(plugins, storage, None)


def bind_plugin_runtime_with_services(
    plugins: list[tuple[Any, Any, Any]],
    storage: ZushStorage,
    service_controller: Any | None,
) -> None:
    owned_services: dict[str, set[str]] = {}
    for path, instance, _commands in plugins:
        plugin_name = str(path.name)
        services = getattr(instance, "services", None)
        if isinstance(services, dict):
            owned_services[plugin_name] = {str(name) for name in services.keys()}
        else:
            owned_services[plugin_name] = set()
    for path, instance, _commands in plugins:
        bind = getattr(instance, "_bind_runtime", None)
        if callable(bind):
            plugin_name = str(path.name)
            bind(plugin_name, storage, service_controller, owned_services.get(plugin_name, set()))


def register_plugin_globals(plugins: list[tuple[Any, Any, Any]]) -> None:
    for _path, instance, _commands in plugins:
        provided = getattr(instance, "provided_globals", None)
        if isinstance(provided, dict):
            for key, value in provided.items():
                g[key] = value
        provided_factories = getattr(instance, "provided_factories", None)
        if isinstance(provided_factories, dict):
            for key, spec in provided_factories.items():
                if not isinstance(spec, dict):
                    continue
                factory = spec.get("factory")
                if callable(factory):
                    runtime = getattr(instance, "runtime", None)
                    service = spec.get("service") if isinstance(spec.get("service"), str) else None
                    g.register_provider(
                        key,
                        _bind_factory(factory, runtime, service=service),
                        service=service,
                        recreate_on_restart=bool(spec.get("recreate_on_restart", False)),
                        teardown=spec.get("teardown") if callable(spec.get("teardown")) else None,
                    )


def _bind_factory(factory: Any, runtime: Any, service: str | None = None) -> Any:
    def invoke() -> Any:
        if service is not None and runtime is not None:
            runtime.ensure_service(service)
        try:
            signature = inspect.signature(factory)
        except (TypeError, ValueError):
            return factory(runtime)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if not positional:
            return factory()
        return factory(runtime)

    return invoke
