from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from zush import paths
from zush.runtime import g

if TYPE_CHECKING:
    from zush.paths import ZushStorage


Healthcheck = Callable[[dict[str, Any]], bool | tuple[bool, str]]


@dataclass
class ServiceDefinition:
    command: list[str]
    cwd: str | None = None
    env: dict[str, str] | None = None
    auto_restart: bool = False
    healthcheck: Healthcheck | None = None
    control: Any | None = None
    terminate_fallback: bool = True


class ServiceControlRuntime:
    def __init__(
        self,
        controller: ServiceController,
        name: str,
        data: dict[str, Any],
        entry: dict[str, Any],
        definition: ServiceDefinition,
    ) -> None:
        self._controller = controller
        self.name = name
        self._data = data
        self.state = entry
        self.definition = definition

    def save(self) -> None:
        self._controller._save(self._data)

    def default_start(self) -> str:
        return self._controller._start_default(self.name, self._data, self.state, self.definition)

    def default_stop(self) -> str:
        return self._controller._stop_default(self.name, self._data, self.state, self.definition)

    def default_restart(self) -> str:
        return self._controller._restart_default(self.name, self._data, self.state, self.definition)

    def default_status(self) -> str:
        return self._controller._status_default(self.name, self._data, self.state, self.definition)

    def spawn(self) -> int:
        return self._controller._spawn(self.name, self.state)

    def terminate(self) -> None:
        pid = self.state.get("pid")
        if isinstance(pid, int) and self._controller._is_running(pid):
            self._controller._terminate(pid)

    def is_running(self) -> bool:
        pid = self.state.get("pid")
        return isinstance(pid, int) and self._controller._is_running(pid)

    def health(self) -> tuple[bool, str]:
        return self._controller._health(self.name, self.state)


def read_service_registry(storage: ZushStorage | None = None) -> dict[str, Any]:
    file_path = storage.services_file() if storage is not None else paths.services_file()
    if not file_path.exists():
        return {"services": {}}
    try:
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"services": {}}
    if not isinstance(data, dict):
        return {"services": {}}
    services = data.get("services")
    if not isinstance(services, dict):
        data["services"] = {}
    return data


def write_service_registry(data: dict[str, Any], storage: ZushStorage | None = None) -> None:
    file_path = storage.services_file() if storage is not None else paths.services_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def collect_plugin_services(
    plugins: list[tuple[Path, object, dict[str, Any]]],
) -> dict[str, tuple[str, ServiceDefinition]]:
    service_definitions: dict[str, tuple[str, ServiceDefinition]] = {}
    for path, instance, _commands in plugins:
        services = getattr(instance, "services", None)
        if not isinstance(services, dict):
            continue
        for name, service in services.items():
            if name in service_definitions or not isinstance(service, ServiceDefinition):
                continue
            service_definitions[name] = (path.name, service)
    return service_definitions


def sync_service_registry(
    storage: ZushStorage,
    service_definitions: dict[str, tuple[str, ServiceDefinition]],
) -> dict[str, Any]:
    data = read_service_registry(storage)
    services = data.setdefault("services", {})
    for name, (owner, service) in service_definitions.items():
        previous = services.get(name)
        if not isinstance(previous, dict):
            previous = {}
        preserved = {
            key: value
            for key, value in previous.items()
            if key not in {"plugin", "command", "cwd", "env", "auto_restart", "pid", "desired", "last_status", "terminate_fallback"}
        }
        services[name] = {
            **preserved,
            "plugin": owner,
            "command": list(service.command),
            "cwd": service.cwd,
            "env": dict(service.env or {}),
            "auto_restart": service.auto_restart,
            "pid": previous.get("pid"),
            "desired": bool(previous.get("desired", False)),
            "last_status": previous.get("last_status", "stopped"),
            "terminate_fallback": service.terminate_fallback,
        }
    write_service_registry(data, storage)
    return data


class ServiceController:
    def __init__(
        self,
        storage: ZushStorage,
        service_definitions: dict[str, tuple[str, ServiceDefinition]],
    ) -> None:
        self._storage = storage
        self._definitions = service_definitions
        sync_service_registry(storage, service_definitions)

    def list_services(self) -> list[str]:
        data = read_service_registry(self._storage)
        services = data.get("services")
        if not isinstance(services, dict):
            return []
        return sorted(services.keys())

    def start(self, name: str) -> str:
        data, entry = self._load_entry(name)
        definition = self._definition_for_name(name, entry)
        control = getattr(definition.control, "start", None)
        if callable(control):
            runtime = ServiceControlRuntime(self, name, data, entry, definition)
            result = control(runtime)
            entry["desired"] = True
            entry["last_status"] = "running"
            self._save(data)
            g.invalidate_service(name)
            return str(result or f"started {name}")
        return self._start_default(name, data, entry, definition)

    def stop(self, name: str) -> str:
        data, entry = self._load_entry(name)
        definition = self._definition_for_name(name, entry)
        control = getattr(definition.control, "stop", None)
        if callable(control):
            runtime = ServiceControlRuntime(self, name, data, entry, definition)
            result = control(runtime)
            if definition.terminate_fallback:
                runtime.terminate()
            entry["pid"] = None
            entry["desired"] = False
            entry["last_status"] = "stopped"
            self._save(data)
            g.invalidate_service(name)
            return str(result or f"stopped {name}")
        return self._stop_default(name, data, entry, definition)

    def restart(self, name: str) -> str:
        data, entry = self._load_entry(name)
        definition = self._definition_for_name(name, entry)
        control = getattr(definition.control, "restart", None)
        if callable(control):
            runtime = ServiceControlRuntime(self, name, data, entry, definition)
            result = control(runtime)
            entry["desired"] = True
            entry["last_status"] = "running"
            self._save(data)
            g.invalidate_service(name)
            return str(result or f"restarted {name}")
        return self._restart_default(name, data, entry, definition)

    def status(self, name: str) -> str:
        data, entry = self._load_entry(name)
        definition = self._definition_for_name(name, entry)
        control = getattr(definition.control, "status", None)
        if callable(control):
            runtime = ServiceControlRuntime(self, name, data, entry, definition)
            result = control(runtime)
            if isinstance(result, tuple):
                healthy = bool(result[0])
                detail = str(result[1])
                if not healthy and bool(entry.get("desired", False)) and bool(entry.get("auto_restart", False)):
                    restart_result = self.restart(name)
                    return restart_result.replace("started", "restarted", 1)
                entry["last_status"] = detail if healthy else "unhealthy"
                self._save(data)
                return detail if healthy else f"unhealthy {name}: {detail}"
            if isinstance(result, bool):
                if not result and bool(entry.get("desired", False)) and bool(entry.get("auto_restart", False)):
                    restart_result = self.restart(name)
                    return restart_result.replace("started", "restarted", 1)
                entry["last_status"] = "healthy" if result else "unhealthy"
                self._save(data)
                return "healthy" if result else f"unhealthy {name}"
            if result is not None:
                entry["last_status"] = str(result)
                self._save(data)
                return str(result)
        return self._status_default(name, data, entry, definition)

    def ensure_service(self, name: str, timeout: float = 5.0, interval: float = 0.05) -> str:
        data, entry = self._load_entry(name)
        definition = self._definition_for_name(name, entry)
        control_status = getattr(definition.control, "status", None)
        current = self.status(name)
        normalized = current.lower()
        if "healthy" in normalized or normalized == "running":
            return current

        result = self.start(name)
        if definition.healthcheck is None and not callable(control_status):
            return result

        deadline = time.monotonic() + timeout
        last_status = result
        while time.monotonic() < deadline:
            current = self.status(name)
            normalized = current.lower()
            if "healthy" in normalized or normalized == "running":
                return current
            last_status = current
            time.sleep(interval)
        raise TimeoutError(f"Service '{name}' did not become ready: {last_status}")

    def _start_default(
        self,
        name: str,
        data: dict[str, Any],
        entry: dict[str, Any],
        definition: ServiceDefinition,
    ) -> str:
        pid = entry.get("pid")
        if isinstance(pid, int) and self._is_running(pid):
            healthy, _detail = self._health(name, entry)
            if healthy:
                entry["desired"] = True
                entry["last_status"] = "running"
                self._save(data)
                return f"running {name}"
            self._terminate(pid)
        new_pid = self._spawn(name, entry)
        entry["pid"] = new_pid
        entry["desired"] = True
        entry["last_status"] = "running"
        self._save(data)
        g.invalidate_service(name)
        return f"started {name} ({new_pid})"

    def _stop_default(
        self,
        name: str,
        data: dict[str, Any],
        entry: dict[str, Any],
        definition: ServiceDefinition,
    ) -> str:
        pid = entry.get("pid")
        if isinstance(pid, int) and self._is_running(pid):
            self._terminate(pid)
        entry["pid"] = None
        entry["desired"] = False
        entry["last_status"] = "stopped"
        self._save(data)
        g.invalidate_service(name)
        return f"stopped {name}"

    def _restart_default(
        self,
        name: str,
        data: dict[str, Any],
        entry: dict[str, Any],
        definition: ServiceDefinition,
    ) -> str:
        self._stop_default(name, data, entry, definition)
        self._start_default(name, data, entry, definition)
        return f"restarted {name}"

    def _status_default(
        self,
        name: str,
        data: dict[str, Any],
        entry: dict[str, Any],
        definition: ServiceDefinition,
    ) -> str:
        pid = entry.get("pid")
        desired = bool(entry.get("desired", False))
        auto_restart = bool(entry.get("auto_restart", False))

        if not isinstance(pid, int) or not self._is_running(pid):
            if desired and auto_restart:
                result = self.start(name)
                return result.replace("started", "restarted", 1)
            status = "missing" if desired else "stopped"
            entry["last_status"] = status
            self._save(data)
            return status

        healthy, detail = self._health(name, entry)
        if not healthy:
            if desired and auto_restart:
                self._terminate(pid)
                result = self.start(name)
                return result.replace("started", "restarted", 1)
            entry["last_status"] = "unhealthy"
            self._save(data)
            return f"unhealthy {name}: {detail}"

        entry["last_status"] = "healthy"
        self._save(data)
        return "healthy"

    def _load_entry(self, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        data = read_service_registry(self._storage)
        services = data.get("services")
        if not isinstance(services, dict) or name not in services or not isinstance(services[name], dict):
            raise KeyError(f"Unknown service '{name}'")
        return data, services[name]

    def _save(self, data: dict[str, Any]) -> None:
        write_service_registry(data, self._storage)

    def _spawn(self, name: str, entry: dict[str, Any]) -> int:
        definition = self._definition_for_name(name, entry)
        env = os.environ.copy()
        if definition.env:
            env.update({str(key): str(value) for key, value in definition.env.items()})
        kwargs: dict[str, Any] = {
            "cwd": definition.cwd,
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(definition.command, **kwargs)
        return process.pid

    def _definition_for_name(self, name: str, entry: dict[str, Any]) -> ServiceDefinition:
        registered = self._definitions.get(name)
        if registered is not None:
            return registered[1]
        command = entry.get("command")
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise KeyError(f"Unknown service '{name}'")
        env = entry.get("env")
        normalized_env = env if isinstance(env, dict) else {}
        return ServiceDefinition(
            command=command,
            cwd=entry.get("cwd") if isinstance(entry.get("cwd"), str) else None,
            env={str(key): str(value) for key, value in normalized_env.items()},
            auto_restart=bool(entry.get("auto_restart", False)),
            terminate_fallback=bool(entry.get("terminate_fallback", True)),
        )

    def _health(self, name: str, entry: dict[str, Any]) -> tuple[bool, str]:
        registered = self._definitions.get(name)
        if registered is None:
            return True, "running"
        definition = registered[1]
        if definition.healthcheck is None:
            return True, "running"
        result = definition.healthcheck(dict(entry))
        if isinstance(result, tuple):
            return bool(result[0]), str(result[1])
        return bool(result), "healthy" if result else "unhealthy"

    def _is_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _terminate(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
