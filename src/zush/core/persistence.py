"""Persisted plugin configuration via cfg-index.json and cfg payload files."""

from __future__ import annotations

import io
import json
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

from zush.core import storage as _storage
from zush.utils.persistence import (
    cfg_base_dir as _cfg_base_dir,
    payload_type as _payload_type,
    read_plain as _read_plain,
    read_structured as _read_structured,
    write_plain as _write_plain,
    write_structured as _write_structured,
)

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


storage = _storage


def read_cfg_index(storage: ZushStorage | None = None) -> dict[str, Any]:
    """Read cfg-index.json. Returns a normalized empty structure if missing or invalid."""
    file_path = storage.cfg_index_file() if storage is not None else _storage.cfg_index_file()
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
    file_path = storage.cfg_index_file() if storage is not None else _storage.cfg_index_file()
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
