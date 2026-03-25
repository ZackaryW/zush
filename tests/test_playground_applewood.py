from __future__ import annotations

from pathlib import Path

from tests.playground_helpers import (
    make_subprocess_env,
    make_test_home,
    run_zush,
    write_applewood_fixture,
    write_config,
)


def _run_zush(tmp_path: Path, *args: str):
    env_root = tmp_path / "applewood-env"
    write_applewood_fixture(env_root)
    home = make_test_home()
    write_config(home, 'envs = []\nenv_prefix = ["applewood_"]\ninclude_current_env = false\n')
    return run_zush(env_root, *args, env=make_subprocess_env(home=home), timeout=20)


def test_applewood_tree_appears_in_self_map(tmp_path: Path) -> None:
    result = _run_zush(tmp_path, "self", "map")
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "applewood" in output
    assert "find" in output
    assert "move" in output
    assert "copy" in output


def test_applewood_help_shows_commands(tmp_path: Path) -> None:
    result = _run_zush(tmp_path, "applewood", "--help")
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "find" in output
    assert "move" in output
    assert "copy" in output


def test_applewood_find_surfaces_config_errors(tmp_path: Path) -> None:
    image_dir = tmp_path / "photos"
    image_dir.mkdir()
    config_path = tmp_path / "missing.json"

    result = _run_zush(tmp_path, "applewood", "find", str(image_dir), "--config", str(config_path))
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Config file not found" in output