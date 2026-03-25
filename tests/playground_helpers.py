from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYGROUND_ROOT = REPO_ROOT / "playground"


def make_test_home() -> Path:
    home = Path(tempfile.mkdtemp())
    (home / ".zush").mkdir(parents=True, exist_ok=True)
    return home


def write_config(home: Path, content: str) -> Path:
    config_path = home / ".zush" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")
    return config_path


def make_subprocess_env(home: Path | None = None, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if home is not None:
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
    if extra:
        env.update(extra)
    return env


def copy_playground(tmp_path: Path, *plugin_names: str) -> Path:
    target = tmp_path / "playground"
    target.mkdir(parents=True, exist_ok=True)
    names = plugin_names or tuple(
        child.name for child in PLAYGROUND_ROOT.iterdir() if child.is_dir() and child.name != "__pycache__"
    )
    for name in names:
        shutil.copytree(
            PLAYGROUND_ROOT / name,
            target / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    return target


def run_zush(mock_path: Path, *args: str, env: dict[str, str] | None = None, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    cmd = ["uv", "run", "zush", "--mock-path", str(mock_path)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=timeout,
    )


def write_applewood_fixture(env_root: Path) -> Path:
    package_dir = env_root / "applewood_demo"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__zush__.py").write_text(
        """
from __future__ import annotations

import click


@click.command("find")
@click.argument("image_dir", type=click.Path(path_type=str))
@click.option("--config", "config_path", type=click.Path(path_type=str), required=True)
def find_cmd(image_dir: str, config_path: str) -> None:
    from pathlib import Path

    if not Path(config_path).exists():
        raise click.ClickException("Config file not found")
    click.echo(f"find {image_dir} using {config_path}")


@click.command("move")
def move_cmd() -> None:
    click.echo("move")


@click.command("copy")
def copy_cmd() -> None:
    click.echo("copy")


applewood = click.Group("applewood", help="Applewood demo commands")
applewood.add_command(find_cmd, "find")
applewood.add_command(move_cmd, "move")
applewood.add_command(copy_cmd, "copy")


class _Plugin:
    def __init__(self) -> None:
        self.commands = {"applewood": applewood}


ZushPlugin = _Plugin()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return package_dir
