from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from zush import paths

if TYPE_CHECKING:
    from zush.paths import ZushStorage


def cfg_base_dir(storage: ZushStorage | None) -> Path:
    return storage.cfg_dir() if storage is not None else paths.cfg_dir()


def payload_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    return "plain"


def read_plain(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_plain(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def read_structured(path: Path, data_type: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        if data_type == "json":
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        elif data_type == "toml":
            import tomllib

            with open(path, "rb") as handle:
                data = tomllib.load(handle)
        else:
            with open(path, encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
    except (OSError, json.JSONDecodeError, ValueError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def write_structured(path: Path, data: dict[str, Any], data_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if data_type == "json":
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        return
    if data_type == "toml":
        path.write_text(dump_toml(data), encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    append_toml_table(lines, data, prefix="")
    return "\n".join(lines).rstrip() + "\n"


def append_toml_table(lines: list[str], data: dict[str, Any], prefix: str) -> None:
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
        lines.append(f"{key} = {toml_value(value)}")
    if scalars and tables:
        lines.append("")
    for index, (key, value) in enumerate(tables):
        table_name = f"{prefix}.{key}" if prefix else key
        append_toml_table(lines, value, table_name)
        if index != len(tables) - 1:
            lines.append("")


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value))
