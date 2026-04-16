"""Tests for zush.core.envs helpers."""

from pathlib import Path

import pytest

from zush.core import envs


def test_current_site_package_dirs_returns_paths(monkeypatch, tmp_path):
    """Helper should return de-duplicated existing paths."""

    # Arrange fake site/sysconfig values pointing at temp dirs
    site_dir = tmp_path / "site"
    pure_dir = tmp_path / "pure"
    plat_dir = tmp_path / "plat"
    user_dir = tmp_path / "user"
    for d in (site_dir, pure_dir, plat_dir, user_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        envs.site,
        "getsitepackages",
        lambda: [str(site_dir)],
        raising=False,
    )

    def fake_get_paths():
        return {"purelib": str(pure_dir), "platlib": str(plat_dir)}

    monkeypatch.setattr(envs.sysconfig, "get_paths", fake_get_paths, raising=False)
    monkeypatch.setattr(
        envs.site,
        "getusersitepackages",
        lambda: str(user_dir),
        raising=False,
    )

    # Act
    result = envs.current_site_package_dirs()

    # Assert
    assert isinstance(result, list)
    assert all(isinstance(p, Path) for p in result)
    # All four dirs should be present, with no duplicates
    assert site_dir.resolve() in result
    assert pure_dir.resolve() in result
    assert plat_dir.resolve() in result
    assert user_dir.resolve() in result
    assert len(result) == 4


def test_current_site_package_dirs_tolerates_expected_lookup_failures(monkeypatch, tmp_path):
    """Expected lookup failures should degrade gracefully while still returning other valid paths."""
    pure_dir = tmp_path / "pure"
    pure_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        envs.site,
        "getsitepackages",
        lambda: (_ for _ in ()).throw(OSError("site unavailable")),
        raising=False,
    )
    monkeypatch.setattr(
        envs.sysconfig,
        "get_paths",
        lambda: {"purelib": str(pure_dir)},
        raising=False,
    )
    monkeypatch.setattr(
        envs.site,
        "getusersitepackages",
        lambda: (_ for _ in ()).throw(AttributeError("no user site")),
        raising=False,
    )

    result = envs.current_site_package_dirs()

    assert result == [pure_dir.resolve()]


def test_current_site_package_dirs_propagates_unexpected_errors(monkeypatch):
    """Unexpected runtime failures during environment lookup should not be silently swallowed."""
    monkeypatch.setattr(
        envs.site,
        "getsitepackages",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        envs.current_site_package_dirs()

