from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from zush.errors import ZushError


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def load_namespaces(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload["namespaces"]
        if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
            raise TypeError
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ZushError(f"invalid namespace state at {path}") from error
    return set(values)


def save_namespaces(path: Path, owners: set[str]) -> None:
    if any(not isinstance(owner, str) or not owner for owner in owners):
        raise ZushError("namespace owners must be nonempty strings")
    atomic_write_text(path, json.dumps({"namespaces": sorted(owners)}, indent=2) + "\n")
