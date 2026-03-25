from __future__ import annotations

import types
from pathlib import Path

import click
from click.testing import CliRunner

from zush.config import Config
from zush.utils.cli import parse_mock_path
from zush.utils.discovery import build_envs_to_scan, cached_package_paths_for_env, merge_commands_into_tree, scan_env_for_plugins
from zush.utils.group import command_path, merge_commands_into_group, print_command_tree
from zush.utils.persistence import dump_toml
from zush.utils.plugin_loader import find_plugin_instance


def test_parse_mock_path_strips_flag_and_value() -> None:
    mock_path, argv = parse_mock_path(["--mock-path", "demo", "self", "map"])

    assert mock_path == Path("demo")
    assert argv == ["self", "map"]


def test_find_plugin_instance_prefers_named_zush_plugin() -> None:
    preferred = types.SimpleNamespace(commands={"a": object()})
    fallback = types.SimpleNamespace(commands={"b": object()})
    module = types.ModuleType("demo")
    module.ZushPlugin = preferred
    module.other = fallback

    assert find_plugin_instance(module) is preferred


def test_merge_commands_into_tree_and_recover_cached_paths(tmp_path: Path) -> None:
    env_root = tmp_path / "env"
    pkg = env_root / "zush_demo"
    pkg.mkdir(parents=True)
    tree: dict[str, object] = {}

    merge_commands_into_tree(tree, {"demo.greet": object(), "demo.nested.run": object()}, str(pkg.resolve()))

    assert cached_package_paths_for_env(tree, env_root) == [pkg.resolve()]


def test_build_envs_to_scan_respects_mock_path_and_config_order(tmp_path: Path) -> None:
    playground = tmp_path / "playground"
    env_root = tmp_path / "env"
    current = tmp_path / "current"
    playground.mkdir()
    env_root.mkdir()
    current.mkdir()
    config = Config(
        envs=[env_root],
        env_prefix=["zush_"],
        playground=playground,
        include_current_env=True,
    )

    envs_to_scan = build_envs_to_scan(config, current_site_package_dirs=lambda: [current])

    assert envs_to_scan == [playground, current, env_root]
    assert build_envs_to_scan(config, mock_path=env_root, current_site_package_dirs=lambda: [current]) == [env_root]


def test_scan_env_for_plugins_collects_plugins_and_cache_entries(tmp_path: Path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    package_dir = env_root / "zush_demo"
    package_dir.mkdir()
    (package_dir / "__zush__.py").write_text(
        """
import click
plugin = type("Plugin", (), {"commands": {"demo.greet": click.Command("greet")}})()
""",
        encoding="utf-8",
    )
    plugins: list[tuple[Path, object, dict[str, object]]] = []
    merged_tree: dict[str, object] = {}
    cache_entries: list[dict[str, object]] = []

    scan_env_for_plugins(
        env_root,
        ["zush_"],
        plugins,
        merged_tree,
        cache_entries,
        merge_commands_into_tree,
    )

    assert len(plugins) == 1
    assert plugins[0][0] == package_dir
    assert "demo" in merged_tree
    assert any(entry.get("root") is True for entry in cache_entries)
    assert any(entry.get("package") == "zush_demo" for entry in cache_entries)


def test_group_utils_merge_and_print_tree() -> None:
    root = click.Group("zush")
    merge_commands_into_group(root, [("/demo", None, {"demo.greet": click.Command("greet")})])

    @click.command(
        "show",
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    @click.pass_context
    def show(ctx: click.Context) -> None:
        click.echo(".".join(command_path(ctx)))

    root.add_command(show, "show")
    runner = CliRunner()

    result = runner.invoke(root, ["show", "alpha", "beta"], standalone_mode=False)
    assert result.exit_code == 0
    assert "alpha.beta" in result.output

    lines: list[str] = []
    original_echo = click.echo
    click.echo = lambda message="", **kwargs: lines.append(str(message))
    try:
        print_command_tree(root, "")
    finally:
        click.echo = original_echo
    output = "\n".join(lines)

    assert "demo" in output
    assert "greet" in output


def test_dump_toml_renders_nested_tables() -> None:
    body = dump_toml({"enabled": True, "nested": {"count": 2}})

    assert "enabled = true" in body
    assert "[nested]" in body
    assert "count = 2" in body
