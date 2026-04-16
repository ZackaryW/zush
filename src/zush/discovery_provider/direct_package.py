"""Discovery provider for env paths that are themselves plugin package roots."""

from __future__ import annotations

from pathlib import Path

from zush.discovery_provider.base import DiscoveryCandidate, DiscoveryDiagnostic, DiscoveryReport


class DirectPackageDiscoveryProvider:
    """Treats the env path itself as the candidate package root when it matches zush rules."""

    def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
        """Return True when the env path signature matches a direct plugin package root."""
        extension_key = self.resolve_extension_key(env_path)
        return any(extension_key.startswith(prefix) for prefix in env_prefixes)

    def discover(
        self,
        env_path: Path,
        env_prefixes: list[str],
        disabled_extensions: set[str] | None = None,
    ) -> DiscoveryReport:
        """Return one candidate when the env path is itself an enabled plugin package root."""
        extension_key = self.resolve_extension_key(env_path)
        disabled = disabled_extensions or set()
        if extension_key in disabled:
            return DiscoveryReport(candidates=[], diagnostics=[])
        if not any(extension_key.startswith(prefix) for prefix in env_prefixes):
            return DiscoveryReport(candidates=[], diagnostics=[])
        if not (env_path / "__zush__.py").exists():
            return DiscoveryReport(
                candidates=[],
                diagnostics=[
                    DiscoveryDiagnostic(
                        source="provider",
                        code="package-entrypoint-missing",
                        message="No __zush__.py found in direct package root",
                        env_path=env_path,
                        package_path=env_path,
                        extension_key=extension_key,
                    )
                ],
            )
        return DiscoveryReport(
            candidates=[DiscoveryCandidate(package_path=env_path, extension_key=extension_key)],
            diagnostics=[],
        )

    def discover_candidates(
        self,
        env_path: Path,
        env_prefixes: list[str],
        disabled_extensions: set[str] | None = None,
    ) -> list[DiscoveryCandidate]:
        """Compatibility helper returning only candidates for older internal call sites."""
        return self.discover(env_path, env_prefixes, disabled_extensions=disabled_extensions).candidates

    def resolve_extension_key(self, package_path: Path) -> str:
        """Return the stable extension key for a direct package root."""
        return package_path.name