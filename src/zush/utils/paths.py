from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ZushPaths:
    home: Path
    namespaces: Path
    aliases: Path
    bucket: Path
    saucepan: Path
    binary: Path

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ZushPaths:
        values = os.environ if environment is None else environment
        home = Path(values["ZUSH_HOME"]) if values.get("ZUSH_HOME") else Path.home() / ".zush"
        return cls(
            home=home,
            namespaces=home / "namespaces.json",
            aliases=home / "aliases.json",
            bucket=home / "generated-index" / "bucket.json",
            saucepan=home / "saucepan",
            binary=home / "bin" / ("saucepan.exe" if os.name == "nt" else "saucepan"),
        )
