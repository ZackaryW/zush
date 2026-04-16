"""Base types for zush discovery providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class DiscoveryCandidate:
    """Represents one discovered plugin package candidate before plugin loading."""

    package_path: Path
    extension_key: str


@dataclass(frozen=True)
class DiscoveryDiagnostic:
    """Describes one non-fatal discovery event that callers may want to surface later."""

    source: str
    code: str
    message: str
    env_path: Path | None = None
    package_path: Path | None = None
    extension_key: str | None = None


@dataclass(frozen=True)
class DiscoveryReport:
    """Bundles discovered candidates together with provider-level diagnostics."""

    candidates: list[DiscoveryCandidate]
    diagnostics: list[DiscoveryDiagnostic]


class DiscoveryProvider(Protocol):
    """Describes a strategy that enumerates plugin package candidates for one env root."""

    def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
        """Return True when this provider should handle the given env path."""
        ...

    def discover(
        self,
        env_path: Path,
        env_prefixes: list[str],
        disabled_extensions: set[str] | None = None,
    ) -> DiscoveryReport:
        """Return enabled package candidates plus provider-level diagnostics."""
        ...
