"""Tests for zush.envs helpers."""

from pathlib import Path

import pytest

from zush import envs


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

