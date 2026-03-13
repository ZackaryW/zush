"""Persisted plugin configuration via cfg-index.json and cfg payload files."""

from __future__ import annotations

import io
import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

import yaml

from zush import paths

if TYPE_CHECKING:
    from zush.paths import ZushStorage


def read_cfg_index(storage: ZushStorage | None = None) -> dict[str, Any]:
    """Read cfg-index.json. Returns a normalized empty structure if missing or invalid."""
    file_path = storage.cfg_index_file() if storage is not None else paths.cfg_index_file()
    if not file_path.exists():
        return {"plugins": {}}
    try:
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"plugins": {}}
    if not isinstance(data, dict):
        return {"plugins": {}}
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        data["plugins"] = {}
    return data


def write_cfg_index(data: dict[str, Any], storage: ZushStorage | None = None) -> None:
    """Write cfg-index.json, creating parent directories when needed."""
    file_path = storage.cfg_index_file() if storage is not None else paths.cfg_index_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def ensure_plugin_cfg_entry(
    plugin_name: str,
    storage: ZushStorage | None = None,
    default_file: str = "zush.json",
) -> dict[str, Any]:
    """Ensure a plugin has a cfg index entry and payload directory."""
    data = read_cfg_index(storage=storage)
    plugins = data.setdefault("plugins", {})
    entry = plugins.get(plugin_name)
    if not isinstance(entry, dict):
        entry = {}
        plugins[plugin_name] = entry
    cfg_uuid = entry.get("uuid")
    if not isinstance(cfg_uuid, str) or not cfg_uuid:
        cfg_uuid = str(uuid.uuid4())
        entry["uuid"] = cfg_uuid
    if not isinstance(entry.get("default_file"), str) or not entry.get("default_file"):
        entry["default_file"] = default_file
    write_cfg_index(data, storage=storage)
    target_dir = _cfg_base_dir(storage) / cfg_uuid
    target_dir.mkdir(parents=True, exist_ok=True)
    return entry


@contextmanager
def persisted_ctx(
    plugin_name: str,
    storage: ZushStorage,
    filename: str | None = None,
    default_file: str = "zush.json",
) -> Iterator[dict[str, Any] | io.StringIO]:
    """Yield a mutable object backed by a persisted file for the given plugin."""
    entry = ensure_plugin_cfg_entry(plugin_name, storage=storage, default_file=default_file)
    resolved_name = filename or str(entry.get("default_file") or default_file)
    target = _cfg_base_dir(storage) / str(entry["uuid"]) / resolved_name
    payload_type = _payload_type(resolved_name)
    if payload_type == "plain":
        buffer = io.StringIO(_read_plain(target))
        try:
            yield buffer
        finally:
            _write_plain(target, buffer.getvalue())
        return

    data = _read_structured(target, payload_type)
    try:
        yield data
    finally:
        _write_structured(target, data, payload_type)


def _cfg_base_dir(storage: ZushStorage | None) -> Path:
    return storage.cfg_dir() if storage is not None else paths.cfg_dir()


def _payload_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    return "plain"


def _read_plain(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_plain(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _read_structured(path: Path, payload_type: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        if payload_type == "json":
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        elif payload_type == "toml":
            import tomllib

            with open(path, "rb") as handle:
                data = tomllib.load(handle)
        else:
            with open(path, encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
    except (OSError, json.JSONDecodeError, ValueError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_structured(path: Path, data: dict[str, Any], payload_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if payload_type == "json":
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        return
    if payload_type == "toml":
        path.write_text(_dump_toml(data), encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def _dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    _append_toml_table(lines, data, prefix="")
    return "\n".join(lines).rstrip() + "\n"


def _append_toml_table(lines: list[str], data: dict[str, Any], prefix: str) -> None:
    scalars: list[tuple[str, Any]] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    for key, value in data.items():
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            scalars.append((key, value))

    if prefix:
        lines.append(f"[{prefix}]")
    for key, value in scalars:
        lines.append(f"{key} = {_toml_value(value)}")
    if scalars and tables:
        lines.append("")
    for index, (key, value) in enumerate(tables):
        table_name = f"{prefix}.{key}" if prefix else key
        _append_toml_table(lines, value, table_name)
        if index != len(tables) - 1:
            lines.append("")


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value))