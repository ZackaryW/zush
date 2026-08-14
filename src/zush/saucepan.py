from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from zush.errors import IntegrationError, ZushError

PINNED_SAUCEPAN_VERSION = "v0.3.0"
CommandRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class InstalledRepository:
    target: str
    identity: str


def _run(argv: list[str]) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argv, never a shell command
            argv, check=False, capture_output=True, text=True
        )
    except OSError as error:
        raise IntegrationError(f"cannot run Saucepan: {error}") from error
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Saucepan failed"
        raise IntegrationError(detail)
    return completed.stdout


class SaucepanWorkspace:
    def __init__(
        self,
        root: Path,
        *,
        binary: str | Path | None = None,
        run: CommandRunner = _run,
        binary_destination: Path | None = None,
    ) -> None:
        self.root = root
        self._run = run
        self.binary = str(binary or _resolve_binary(binary_destination))
        self._ensure_config()

    def ensure(self, target: str) -> Path:
        installed = self._find(target)
        if installed is None:
            self._command("install", target)
            installed = self._find(target)
        if installed is None:
            raise IntegrationError(f"Saucepan installed {target} without recording its provenance")
        return Path(self._command("path", installed.identity).strip())

    def installed(self) -> list[InstalledRepository]:
        payload = self._json("cat", "index")
        if not isinstance(payload, list):
            raise IntegrationError("Saucepan index is not an array")
        result: list[InstalledRepository] = []
        for entry in payload:
            if not isinstance(entry, dict) or "repo" not in entry:
                continue
            sauce = entry.get("sauce")
            target = entry.get("repo")
            identity = sauce.get("name") if isinstance(sauce, dict) else None
            if not isinstance(target, str) or not isinstance(identity, str):
                raise IntegrationError("Saucepan index contains an invalid GitHub entry")
            result.append(InstalledRepository(target, identity))
        return result

    def update_all(self, visible_targets: set[str]) -> None:
        for entry in self.installed():
            if entry.target in visible_targets:
                self._command("update", entry.identity)

    def uninstall(self, target: str) -> None:
        installed = self._find(target)
        if installed is None:
            raise ZushError(f"repository is not installed: {target}")
        self._command("uninstall", installed.identity)

    def register_index(self, path: Path) -> None:
        payload = self._json("cat", "buckets")
        if not isinstance(payload, list):
            raise IntegrationError("Saucepan bucket registry is not an array")
        target = str(path)
        if not any(isinstance(entry, dict) and entry.get("url") == target for entry in payload):
            self._command("bucket", "add", target)

    def _find(self, target: str) -> InstalledRepository | None:
        return next((entry for entry in self.installed() if entry.target == target), None)

    def _json(self, *args: str) -> object:
        output = self._command(*args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise IntegrationError("Saucepan returned invalid JSON") from error

    def _command(self, *args: str) -> str:
        return self._run([self.binary, str(self.root), *args])

    def _ensure_config(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        config = self.root / "saucepan.toml"
        if not config.exists():
            config.write_text('[github]\nbinary = "gh"\n', encoding="utf-8", newline="\n")


def _resolve_binary(destination: Path | None) -> str:
    explicit = os.environ.get("ZUSH_SAUCEPAN")
    if explicit:
        return explicit
    installed = shutil.which("saucepan")
    if installed:
        return installed
    from zush.vendor.saucepan_resolver import resolve

    target = destination or Path.home() / ".zush" / "bin" / ("saucepan.exe" if os.name == "nt" else "saucepan")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        return str(resolve(PINNED_SAUCEPAN_VERSION, str(target)))
    except (OSError, RuntimeError, ValueError) as error:
        raise IntegrationError(f"cannot acquire Saucepan {PINNED_SAUCEPAN_VERSION}: {error}") from error
