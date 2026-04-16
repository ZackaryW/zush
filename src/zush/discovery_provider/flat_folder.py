"""Flat-folder discovery provider for env roots that contain plugin package directories."""

from __future__ import annotations

from pathlib import Path

from zush.discovery_provider.base import DiscoveryCandidate, DiscoveryDiagnostic, DiscoveryReport


class FlatFolderDiscoveryProvider:
    """Enumerates plugin package directories directly under one env root."""

    def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
        """Return True when the env root looks like a flat folder of plugin package directories."""
        try:
            return any(child.is_dir() and any(child.name.startswith(prefix) for prefix in env_prefixes) for child in env_path.iterdir())
        except OSError:
            return False

    def discover(
        self,
        env_path: Path,
        env_prefixes: list[str],
        disabled_extensions: set[str] | None = None,
    ) -> DiscoveryReport:
        """Return matching enabled package directories and provider-level diagnostics."""
        candidates: list[DiscoveryCandidate] = []
        diagnostics: list[DiscoveryDiagnostic] = []
        disabled = disabled_extensions or set()
        try:
            children = list(env_path.iterdir())
        except OSError as exc:
            diagnostics.append(
                DiscoveryDiagnostic(
                    source="provider",
                    code="env-read-failed",
                    message=str(exc),
                    env_path=env_path,
                )
            )
            return DiscoveryReport(candidates=[], diagnostics=diagnostics)
        for child in children:
            if not child.is_dir():
                continue
            if not any(child.name.startswith(prefix) for prefix in env_prefixes):
                continue
            extension_key = self.resolve_extension_key(child)
            if extension_key in disabled:
                continue
            if not (child / "__zush__.py").exists():
                continue
            candidates.append(DiscoveryCandidate(package_path=child, extension_key=extension_key))
        return DiscoveryReport(candidates=candidates, diagnostics=diagnostics)

    def discover_candidates(
        self,
        env_path: Path,
        env_prefixes: list[str],
        disabled_extensions: set[str] | None = None,
    ) -> list[DiscoveryCandidate]:
        """Compatibility helper returning only candidates for older internal call sites."""
        return self.discover(env_path, env_prefixes, disabled_extensions=disabled_extensions).candidates

    def resolve_extension_key(self, package_path: Path) -> str:
        """Return the stable extension key for one discovered package path."""
        return package_path.name

