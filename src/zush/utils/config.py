from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from zush.errors import ZushError
from zush.utils.addressing import Address, parse_address
from zush.utils.state import atomic_write_text


@dataclass(frozen=True)
class Alias:
    target: Address
    default_args: tuple[str, ...] = ()
    default_map: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Configuration:
    commands: Mapping[str, Alias]
    exclusions: Mapping[str, tuple[str, ...]]


def load_remote_map(path: Path | None) -> Configuration:
    if path is None or not path.exists():
        return Configuration({}, {})
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ZushError(f"invalid remote configuration at {path}: {error}") from error
    try:
        commands_raw = payload.get("commands", {})
        namespaces_raw = payload.get("namespaces", {})
        if not isinstance(commands_raw, dict) or not isinstance(namespaces_raw, dict):
            raise TypeError
        for name in commands_raw:
            _validate_name(name)
        commands = {name: _alias_from_mapping(record) for name, record in commands_raw.items()}
        exclusions: dict[str, tuple[str, ...]] = {}
        for owner, record in namespaces_raw.items():
            values = record.get("exclude", [])
            if not isinstance(owner, str) or not isinstance(record, dict) or not _string_list(values):
                raise TypeError
            exclusions[owner] = tuple(values)
    except (AttributeError, TypeError, ZushError) as error:
        if isinstance(error, ZushError):
            raise
        raise ZushError(f"invalid remote configuration shape at {path}") from error
    return Configuration(commands, exclusions)


def load_local_overlay(path: Path) -> tuple[dict[str, Alias], set[str]]:
    if not path.exists():
        return {}, set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        commands_raw = payload.get("commands", {})
        tombstones_raw = payload.get("tombstones", [])
        if not isinstance(commands_raw, dict) or not _string_list(tombstones_raw):
            raise TypeError
        for name in (*commands_raw, *tombstones_raw):
            _validate_name(name)
        commands = {name: _alias_from_json(record) for name, record in commands_raw.items()}
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ZushError) as error:
        if isinstance(error, ZushError):
            raise
        raise ZushError(f"invalid local alias overlay at {path}") from error
    return commands, set(tombstones_raw)


def merge_configuration(remote: Configuration, local: tuple[dict[str, Alias], set[str]]) -> Configuration:
    local_commands, tombstones = local
    commands = {name: alias for name, alias in remote.commands.items() if name not in tombstones}
    commands.update(local_commands)
    return Configuration(commands, dict(remote.exclusions))


def bind(path: Path, name: str, alias: Alias) -> None:
    _validate_name(name)
    commands, tombstones = load_local_overlay(path)
    commands[name] = alias
    tombstones.discard(name)
    _save_overlay(path, commands, tombstones)


def unbind(path: Path, name: str) -> None:
    _validate_name(name)
    commands, tombstones = load_local_overlay(path)
    commands.pop(name, None)
    tombstones.add(name)
    _save_overlay(path, commands, tombstones)


def _alias_from_mapping(record: object) -> Alias:
    if not isinstance(record, dict):
        raise ZushError("alias record must be a table")
    target = record.get("target")
    if not isinstance(target, dict):
        raise ZushError("alias target must be a table")
    owner = target.get("owner")
    repository = target.get("repo")
    path = target.get("path")
    if not isinstance(owner, str) or not isinstance(repository, str) or not isinstance(path, str):
        raise ZushError("alias target requires owner, repo, and path strings")
    address = parse_address(f"~{repository}:{path}" if owner == "~" else f"{owner}/{repository}:{path}")
    default_args = record.get("default_args", [])
    default_map = record.get("default_map", {})
    if not _string_list(default_args) or not isinstance(default_map, dict):
        raise ZushError("alias defaults require a string array and a table")
    try:
        json.dumps(default_map)
    except (TypeError, ValueError) as error:
        raise ZushError("alias default_map must contain JSON-compatible values") from error
    return Alias(address, tuple(default_args), default_map)


def _alias_from_json(record: object) -> Alias:
    if not isinstance(record, dict):
        raise ZushError("local alias must be an object")
    target = record.get("target")
    if not isinstance(target, dict):
        raise ZushError("local alias target must be an object")
    owner = target.get("owner")
    repository = target.get("repository")
    script = target.get("script")
    if owner is not None and not isinstance(owner, str):
        raise ZushError("local alias owner must be a string or null")
    if not isinstance(repository, str) or not _string_list(script):
        raise ZushError("local alias target is invalid")
    default_args = record.get("default_args", [])
    default_map = record.get("default_map", {})
    if not _string_list(default_args) or not isinstance(default_map, dict):
        raise ZushError("local alias defaults are invalid")
    return Alias(Address(owner, repository, tuple(script)), tuple(default_args), default_map)


def _save_overlay(path: Path, commands: dict[str, Alias], tombstones: set[str]) -> None:
    payload = {
        "commands": {
            name: {
                "target": {
                    "owner": alias.target.owner,
                    "repository": alias.target.repository,
                    "script": list(alias.target.script),
                },
                "default_args": list(alias.default_args),
                "default_map": dict(alias.default_map),
            }
            for name, alias in sorted(commands.items())
        },
        "tombstones": sorted(tombstones),
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not name or any(character.isspace() or character in ":/\\" for character in name):
        raise ZushError("alias name must be an unqualified token without ':', '/' or '\\'")
