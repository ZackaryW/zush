from __future__ import annotations

from typing import Any, Callable


class ProviderBinding:
    def __init__(
        self,
        factory: Callable[[], Any],
        service: str | None = None,
        recreate_on_restart: bool = False,
        teardown: Callable[[Any], None] | None = None,
    ) -> None:
        self.factory = factory
        self.service = service
        self.recreate_on_restart = recreate_on_restart
        self.teardown = teardown
        self._resolved = False
        self._value: Any = None

    def get_value(self) -> Any:
        if not self._resolved:
            self._value = self.factory()
            self._resolved = True
        return self._value

    def invalidate(self) -> None:
        if not self._resolved:
            return
        if callable(self.teardown):
            self.teardown(self._value)
        self._value = None
        self._resolved = False


class PluginRuntime:
    def __init__(
        self,
        plugin_name: str,
        storage: Any,
        service_controller: Any | None = None,
        owned_services: set[str] | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.storage = storage
        self._service_controller = service_controller
        self._owned_services = owned_services or set()

    def ensure_service(self, name: str, timeout: float = 5.0, interval: float = 0.05) -> str:
        self._assert_service_access(name)
        if self._service_controller is None:
            raise RuntimeError("Service runtime is not bound")
        return self._service_controller.ensure_service(name, timeout=timeout, interval=interval)

    def start_service(self, name: str) -> str:
        self._assert_service_access(name)
        if self._service_controller is None:
            raise RuntimeError("Service runtime is not bound")
        return self._service_controller.start(name)

    def stop_service(self, name: str) -> str:
        self._assert_service_access(name)
        if self._service_controller is None:
            raise RuntimeError("Service runtime is not bound")
        return self._service_controller.stop(name)

    def restart_service(self, name: str) -> str:
        self._assert_service_access(name)
        if self._service_controller is None:
            raise RuntimeError("Service runtime is not bound")
        return self._service_controller.restart(name)

    def status_service(self, name: str) -> str:
        self._assert_service_access(name)
        if self._service_controller is None:
            raise RuntimeError("Service runtime is not bound")
        return self._service_controller.status(name)

    def _assert_service_access(self, name: str) -> None:
        if self._owned_services and name not in self._owned_services:
            raise KeyError(f"Service '{name}' is not owned by plugin '{self.plugin_name}'")


class GlobalStore(dict[str, Any]):
    """Process-local global object registry for the current zush runtime."""

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        return self._resolve(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self:
            return default
        return self[key]

    def ensure(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self:
            self[key] = factory()
        return self[key]

    def provide_factory(self, key: str, factory: Callable[[], Any]) -> None:
        super().__setitem__(key, ProviderBinding(factory))

    def register_provider(
        self,
        key: str,
        factory: Callable[[], Any],
        service: str | None = None,
        recreate_on_restart: bool = False,
        teardown: Callable[[Any], None] | None = None,
    ) -> None:
        super().__setitem__(
            key,
            ProviderBinding(
                factory,
                service=service,
                recreate_on_restart=recreate_on_restart,
                teardown=teardown,
            ),
        )

    def invalidate_service(self, service: str) -> None:
        for value in super().values():
            if not isinstance(value, ProviderBinding):
                continue
            if value.service != service or not value.recreate_on_restart:
                continue
            value.invalidate()

    def _resolve(self, key: str, value: Any) -> Any:
        if not isinstance(value, ProviderBinding):
            return value
        return value.get_value()


g = GlobalStore()
