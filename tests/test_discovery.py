"""TDD: discovery — scan envs, load plugins, merge tree, update cache/sentry."""

import tempfile
from pathlib import Path

import click
import pytest

from zush.configparse.config import Config
from zush.core.cache import read_cache, read_sentry
from zush.core.discovery import run_discovery
from zush.core.storage import DirectoryStorage
from zush.discovery_provider import DiscoveryCandidate, DiscoveryDiagnostic, DiscoveryReport
from zush.discovery_provider.direct_package import DirectPackageDiscoveryProvider


def test_run_discovery_empty_envs_returns_empty_plugin_list(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr("zush.core.discovery.storage.config_dir", lambda: Path(d))
        cfg = Config(envs=[], env_prefix=["zush_"])
        plugins, _ = run_discovery(cfg)
    assert plugins == []


def test_run_discovery_discovers_plugin_and_updates_cache(monkeypatch):
    with tempfile.TemporaryDirectory() as env_root:
        env_path = Path(env_root)
        pkg = env_path / "zush_foo"
        pkg.mkdir()
        (pkg / "__zush__.py").write_text("""
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""")
        config_dir = Path(tempfile.mkdtemp())
        monkeypatch.setattr("zush.core.discovery.storage.config_dir", lambda: config_dir)
        monkeypatch.setattr("zush.core.discovery.storage.cache_file", lambda: config_dir / "cache.json")
        monkeypatch.setattr("zush.core.discovery.storage.sentry_file", lambda: config_dir / "sentry.json")
        cfg = Config(envs=[env_path], env_prefix=["zush_"])
        plugins, tree = run_discovery(cfg)
    assert len(plugins) == 1
    path, instance, commands = plugins[0]
    assert path == pkg
    assert "hello" in commands
    assert "hello" in tree or any("hello" in str(n) for n in _nodes(tree))
    cache = read_cache()
    assert cache != {}
    sentry = read_sentry()
    assert len(sentry) >= 1


def _nodes(d):
    """Flatten nested dict keys."""
    for k, v in (d or {}).items():
        if k.startswith("_"):
            continue
        yield k
        if isinstance(v, dict):
            yield from _nodes(v)


def test_run_discovery_uses_playground_as_overloaded_index(monkeypatch):
    """When config.playground is set, it is scanned first (overloaded index env)."""
    with tempfile.TemporaryDirectory() as env_root:
        env_path = Path(env_root)
        pkg = env_path / "zush_foo"
        pkg.mkdir()
        (pkg / "__zush__.py").write_text("""
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello", callback=lambda: None)}})()
""")
        config_dir = Path(tempfile.mkdtemp())
        monkeypatch.setattr("zush.core.discovery.storage.config_dir", lambda: config_dir)
        monkeypatch.setattr("zush.core.discovery.storage.cache_file", lambda: config_dir / "cache.json")
        monkeypatch.setattr("zush.core.discovery.storage.sentry_file", lambda: config_dir / "sentry.json")
        cfg = Config(envs=[], env_prefix=["zush_"], playground=env_path)
        plugins, _ = run_discovery(cfg)
    assert len(plugins) == 1
    assert plugins[0][0] == pkg


def test_run_discovery_uses_storage_when_provided(tmp_path):
    """When storage is provided, cache and sentry are read/written via storage."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text("""
import click
plugin = type("P", (), {"commands": {"hi": click.Command("hi")}})()
""")
    storage = DirectoryStorage(tmp_path / "data")
    cfg = Config(envs=[env_root], env_prefix=["zush_"], include_current_env=False)
    plugins, tree = run_discovery(cfg, storage=storage)
    assert len(plugins) == 1
    assert (storage.cache_file()).exists()
    assert (storage.sentry_file()).exists()
    assert read_cache(storage=storage) != {}
    assert len(read_sentry(storage=storage)) >= 1


def test_run_discovery_includes_current_env_when_flag_set(monkeypatch, tmp_path):
    """When include_current_env is True, discovery scans current site-packages (via helper)."""
    # Fake current site-packages to point at our temp env_root
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
"""
    )
    monkeypatch.setattr("zush.core.envs.current_site_package_dirs", lambda: [env_root])
    cfg = Config(envs=[], env_prefix=["zush_"], playground=None, include_current_env=True)
    plugins, _ = run_discovery(cfg)
    assert any(p[0] == pkg for p in plugins)


def test_run_discovery_reloads_cached_plugins_for_unchanged_env(tmp_path):
    """When an env is unchanged, discovery should rebuild live plugins from cache."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
"""
    )
    storage = DirectoryStorage(tmp_path / "data")
    cfg = Config(envs=[env_root], env_prefix=["zush_"], include_current_env=False)

    first_plugins, first_tree = run_discovery(cfg, storage=storage)

    assert len(first_plugins) == 1
    assert "hello" in first_tree

    second_plugins, second_tree = run_discovery(cfg, storage=storage)

    assert len(second_plugins) == 1
    assert second_plugins[0][0] == pkg
    assert "hello" in second_tree


def test_run_discovery_skips_disabled_extensions(tmp_path):
    """Discovery should skip extensions whose resolved package names are disabled."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    enabled_pkg = env_root / "zush_enabled"
    enabled_pkg.mkdir()
    (enabled_pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"enabled": click.Command("enabled")}})()
""",
        encoding="utf-8",
    )
    disabled_pkg = env_root / "zush_disabled"
    disabled_pkg.mkdir()
    (disabled_pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"disabled": click.Command("disabled")}})()
""",
        encoding="utf-8",
    )

    cfg = Config(
        envs=[env_root],
        env_prefix=["zush_"],
        disabled_extensions=["zush_disabled"],
    )

    plugins, tree = run_discovery(cfg, no_cache=True)

    assert [path.name for path, _instance, _commands in plugins] == ["zush_enabled"]
    assert "enabled" in tree
    assert "disabled" not in tree


def test_run_discovery_uses_injected_provider_candidates(tmp_path):
    """Discovery orchestration should load candidates emitted by the injected provider."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "custom_plugin"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""",
        encoding="utf-8",
    )

    class StubProvider:
        """Provider stub used to prove orchestration consumes provider candidates."""

        def discover(
            self,
            env_path: Path,
            env_prefixes: list[str],
            disabled_extensions: set[str] | None = None,
        ) -> DiscoveryReport:
            """Return one explicit candidate regardless of the configured prefix."""
            del env_path, env_prefixes, disabled_extensions
            return DiscoveryReport(
                candidates=[DiscoveryCandidate(package_path=pkg, extension_key="custom_plugin")],
                diagnostics=[],
            )

    cfg = Config(
        envs=[env_root],
        env_prefix=["zush_"],
        include_current_env=False,
    )

    plugins, tree = run_discovery(cfg, no_cache=True, provider=StubProvider())

    assert len(plugins) == 1
    assert plugins[0][0] == pkg
    assert "hello" in tree


def test_run_discovery_collects_provider_and_loader_diagnostics(tmp_path):
    """Discovery should collect provider diagnostics and plugin load failures into an optional sink."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    good_pkg = env_root / "zush_good"
    good_pkg.mkdir()
    (good_pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""",
        encoding="utf-8",
    )
    bad_pkg = env_root / "zush_bad"
    bad_pkg.mkdir()
    (bad_pkg / "__zush__.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    class DiagnosticProvider:
        """Provider stub that emits one provider diagnostic and two package candidates."""

        def discover(
            self,
            env_path: Path,
            env_prefixes: list[str],
            disabled_extensions: set[str] | None = None,
        ) -> DiscoveryReport:
            """Return both candidates and one provider diagnostic for orchestration collection."""
            del env_path, env_prefixes, disabled_extensions
            return DiscoveryReport(
                candidates=[
                    DiscoveryCandidate(package_path=good_pkg, extension_key="zush_good"),
                    DiscoveryCandidate(package_path=bad_pkg, extension_key="zush_bad"),
                ],
                diagnostics=[
                    DiscoveryDiagnostic(
                        source="provider",
                        code="provider-note",
                        message="provider emitted note",
                        env_path=env_root,
                    )
                ],
            )

    cfg = Config(envs=[env_root], env_prefix=["zush_"], include_current_env=False)
    diagnostics: list[DiscoveryDiagnostic] = []

    plugins, tree = run_discovery(
        cfg,
        no_cache=True,
        provider=DiagnosticProvider(),
        diagnostics=diagnostics,
    )

    assert [path.name for path, _instance, _commands in plugins] == ["zush_good"]
    assert "hello" in tree
    assert [diagnostic.code for diagnostic in diagnostics] == ["provider-note", "plugin-load-failed"]
    assert diagnostics[1].package_path == bad_pkg


def test_run_discovery_can_use_direct_package_provider(tmp_path):
    """Discovery should support a provider that treats the env path itself as the plugin package."""
    package_root = tmp_path / "zush_direct"
    package_root.mkdir()
    (package_root / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""",
        encoding="utf-8",
    )
    cfg = Config(envs=[package_root], env_prefix=["zush_"], include_current_env=False)

    plugins, tree = run_discovery(
        cfg,
        no_cache=True,
        provider=DirectPackageDiscoveryProvider(),
    )

    assert len(plugins) == 1
    assert plugins[0][0] == package_root
    assert "hello" in tree


def test_run_discovery_uses_first_matching_provider_for_each_path(tmp_path):
    """Discovery should use the first provider whose identify method matches an env path."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""",
        encoding="utf-8",
    )
    calls: list[str] = []

    class FirstProvider:
        """First matching provider should win and be the only discover call."""

        def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
            del env_path, env_prefixes
            calls.append("first-identify")
            return True

        def discover(
            self,
            env_path: Path,
            env_prefixes: list[str],
            disabled_extensions: set[str] | None = None,
        ) -> DiscoveryReport:
            del env_path, env_prefixes, disabled_extensions
            calls.append("first-discover")
            return DiscoveryReport(
                candidates=[DiscoveryCandidate(package_path=pkg, extension_key="zush_demo")],
                diagnostics=[],
            )

    class SecondProvider:
        """Second provider should not run once the first provider identifies the path."""

        def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
            del env_path, env_prefixes
            calls.append("second-identify")
            return True

        def discover(
            self,
            env_path: Path,
            env_prefixes: list[str],
            disabled_extensions: set[str] | None = None,
        ) -> DiscoveryReport:
            del env_path, env_prefixes, disabled_extensions
            calls.append("second-discover")
            return DiscoveryReport(candidates=[], diagnostics=[])

    cfg = Config(envs=[env_root], env_prefix=["zush_"], include_current_env=False)

    plugins, tree = run_discovery(cfg, no_cache=True, provider=[FirstProvider(), SecondProvider()])

    assert [path.name for path, _instance, _commands in plugins] == ["zush_demo"]
    assert "hello" in tree
    assert calls == ["first-identify", "first-discover"]


def test_run_discovery_skips_non_matching_providers_before_discover(tmp_path):
    """Discovery should call identify first and never call discover on providers that do not match."""
    package_root = tmp_path / "zush_direct"
    package_root.mkdir()
    (package_root / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""",
        encoding="utf-8",
    )
    calls: list[str] = []

    class NonMatchingProvider:
        """A provider that declines the path should never reach discover."""

        def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
            del env_path, env_prefixes
            calls.append("nonmatch-identify")
            return False

        def discover(
            self,
            env_path: Path,
            env_prefixes: list[str],
            disabled_extensions: set[str] | None = None,
        ) -> DiscoveryReport:
            del env_path, env_prefixes, disabled_extensions
            raise AssertionError("discover should not be called for a non-matching provider")

    class MatchingProvider:
        """Second provider handles the path after the first provider declines it."""

        def identify(self, env_path: Path, env_prefixes: list[str]) -> bool:
            del env_path, env_prefixes
            calls.append("match-identify")
            return True

        def discover(
            self,
            env_path: Path,
            env_prefixes: list[str],
            disabled_extensions: set[str] | None = None,
        ) -> DiscoveryReport:
            del env_path, env_prefixes, disabled_extensions
            calls.append("match-discover")
            return DiscoveryReport(
                candidates=[DiscoveryCandidate(package_path=package_root, extension_key="zush_direct")],
                diagnostics=[],
            )

    cfg = Config(envs=[package_root], env_prefix=["zush_"], include_current_env=False)

    plugins, tree = run_discovery(
        cfg,
        no_cache=True,
        provider=[NonMatchingProvider(), MatchingProvider()],
    )

    assert len(plugins) == 1
    assert plugins[0][0] == package_root
    assert "hello" in tree
    assert calls == ["nonmatch-identify", "match-identify", "match-discover"]
