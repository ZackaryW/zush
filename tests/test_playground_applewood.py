from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
APPLEWOOD_SRC = REPO_ROOT.parent.parent / "applewood" / "applewood-letty-chaos-photos" / "src"


def _run_zush(*args: str) -> subprocess.CompletedProcess[str]:
    temp_home = Path(tempfile.mkdtemp())
    config_dir = temp_home / ".zush"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text('envs = []\nenv_prefix = ["applewood_"]\n', encoding="utf-8")
    env = {
        **__import__("os").environ,
        "HOME": str(temp_home),
        "USERPROFILE": str(temp_home),
    }
    cmd = ["uv", "run", "zush", "--mock-path", str(APPLEWOOD_SRC)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=20,
    )


def test_applewood_tree_appears_in_self_map() -> None:
    result = _run_zush("self", "map")
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "applewood" in output
    assert "find" in output
    assert "move" in output
    assert "copy" in output


def test_applewood_help_shows_commands() -> None:
    result = _run_zush("applewood", "--help")
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "find" in output
    assert "move" in output
    assert "copy" in output


def test_applewood_find_surfaces_config_errors(tmp_path: Path) -> None:
    image_dir = tmp_path / "photos"
    image_dir.mkdir()
    config_path = tmp_path / "missing.json"

    result = _run_zush("applewood", "find", str(image_dir), "--config", str(config_path))
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Config file not found" in output