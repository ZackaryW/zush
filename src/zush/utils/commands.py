"""Parse repository-local commands without coupling discovery to acquisition."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from zush.errors import ZushError
from zush.utils.addressing import Address, parse_address
from zush.utils.config import Alias
from zush.utils.scripts import resolve_script


@dataclass(frozen=True)
class Command:
    name: str
    qualified: str
    provenance: str
    alias: Alias
    root: Path | None = None


def load_repository_commands(repository: str, output: Path) -> list[Command]:
    """A local map cannot redirect to a different repository or outside .zush."""
    root = output / ".zush"
    path = root / "map.toml"
    if not root.resolve().is_relative_to(output.resolve()):
        raise ZushError(f"repository command folder escapes output: {repository}: {root}")
    if not path.exists():
        return []
    if not path.resolve().is_relative_to(root.resolve()):
        raise ZushError(f"repository command map escapes .zush: {repository}: {path}")
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        records = payload.get("commands", {})
        if set(payload) - {"commands"} or not isinstance(records, dict):
            raise ValueError("expected only a commands table")
        commands = []
        for name, record in records.items():
            if not name or any(character.isspace() or character in ":/\\" for character in name):
                raise ValueError("command name must be an unqualified token")
            if not isinstance(record, dict) or set(record) - {"path", "default_args", "default_map"}:
                raise ValueError("local commands accept path/default_args/default_map, not cross-repository targets")
            script = record.get("path")
            if not isinstance(script, str):
                raise ValueError("command path must be a dot path string")
            address = parse_address(f"{repository}:{script}")
            args = record.get("default_args", [])
            defaults = record.get("default_map", {})
            if not isinstance(args, list) or any(not isinstance(value, str) for value in args):
                raise ValueError("default_args must be strings")
            if not isinstance(defaults, dict):
                raise ValueError("default_map must be a table")
            json.dumps(defaults, allow_nan=False)
            commands.append(
                Command(name, f"{repository}:{name}", str(path), Alias(address, tuple(args), defaults), root)
            )
        return commands
    except (OSError, ValueError, TypeError, ZushError) as error:
        raise ZushError(f"invalid repository commands for {repository} at {path}: {error}") from error


def select_command(name: str, candidates: list[Command], *, no_first: bool, hidden: set[str]) -> Command:
    matches = [] if name in hidden else [candidate for candidate in candidates if candidate.name == name]
    if not matches:
        raise ZushError(f"unknown alias or command: {name}")
    if no_first and len(matches) > 1:
        details = ", ".join(f"{candidate.qualified} ({candidate.provenance})" for candidate in matches)
        raise ZushError(f"command collision for {name}: {details}; use a qualified name or omit --no-first")
    return matches[0]


def command_script(command: Command) -> Path:
    if command.root is None:
        raise ZushError("global aliases must resolve through their repository")
    script = resolve_script(command.root, command.alias.target.script)
    if not script.resolve().is_relative_to(command.root.resolve()):
        raise ZushError(f"command escapes .zush: {command.qualified}")
    return script


def global_commands(aliases: Mapping[str, Alias], local: Mapping[str, Alias], local_path: Path) -> list[Command]:
    return [
        Command(name, name, str(local_path) if name in local else "central .zush/map.toml", alias)
        for name, alias in sorted(aliases.items())
    ]


def qualified_command(name: str, current: str) -> tuple[Address, str] | None:
    if ":" not in name:
        return None
    target, command = name.split(":", 1)
    address = parse_address(f"{target}:placeholder")
    if not command or any(character in ":/\\" or character.isspace() for character in command):
        raise ZushError("qualified command requires owner/repo:command or ~repo:command")
    return Address(address.owner or current, address.repository, ()), command
