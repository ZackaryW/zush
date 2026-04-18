"""Shared pytest fixtures for cleaning up detached test services."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

import pytest


def _read_service_registry(file_path: Path) -> dict[str, Any]:
    """Read one test-local services registry and return a normalized structure when missing or invalid."""
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


def _is_running(pid: int) -> bool:
    """Return whether one process id still appears alive on the current platform."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_pid(pid: int) -> None:
    """Terminate one detached process tree spawned by the service tests."""
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


def _cleanup_service_registries(base_path: Path) -> None:
    """Terminate any recorded detached service pids under one pytest tmp_path tree."""
    for registry_path in base_path.rglob("services.json"):
        data = _read_service_registry(registry_path)
        services = data.get("services")
        if not isinstance(services, dict):
            continue
        changed = False
        for entry in services.values():
            if not isinstance(entry, dict):
                continue
            pid = entry.get("pid")
            if not isinstance(pid, int) or not _is_running(pid):
                continue
            _terminate_pid(pid)
            entry["pid"] = None
            entry["desired"] = False
            entry["last_status"] = "stopped"
            changed = True
        if not changed:
            continue
        with open(registry_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)


@pytest.fixture(autouse=True)
def cleanup_detached_test_services(request: pytest.FixtureRequest) -> None:
    """Ensure tmp_path-based tests cannot leave detached service processes running after completion."""
    tmp_path = None
    if "tmp_path" in request.fixturenames:
        tmp_path = request.getfixturevalue("tmp_path")
    yield
    if tmp_path is None:
        return
    _cleanup_service_registries(tmp_path)