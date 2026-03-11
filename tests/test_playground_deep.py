"""Verify deep command trees by running the zush CLI (subprocess) against the playground."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYGROUND = REPO_ROOT / "playground"
DEEP_LEAF_MARKER = "ZUSH_DEEP_LEAF_OK"
SHARED_APPENDED_MARKER = "ZUSH_SHARED_APPENDED_FROM_DEEP"
SHARED_HELLO_MARKER = "ZUSH_SHARED_HELLO_FROM_DEMO"


def _run_zush(*args: str) -> subprocess.CompletedProcess:
    """Run zush via uv with --mock-path playground then args."""
    cmd = ["uv", "run", "zush", "--mock-path", str(PLAYGROUND)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=15,
    )


def test_deep_tree_appears_in_self_map() -> None:
    """zush self map includes the deep plugin tree (deep -> a -> b -> c -> d -> leaf)."""
    result = _run_zush("self", "map")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    # Tree should contain the deep path
    assert "deep" in out
    assert "leaf" in out
    # Check nesting: we expect deep, then a, b, c, d, then leaf (order in output may be tree-sorted)
    lines = [line.strip() for line in out.splitlines()]
    # At least these names appear somewhere in the tree
    for name in ("deep", "a", "b", "c", "d", "leaf"):
        assert any(name in line for line in lines), f"Expected '{name}' in self map output"


def test_deep_leaf_command_invokes() -> None:
    """zush deep a b c d leaf runs the leaf command and echoes the marker."""
    result = _run_zush("deep", "a", "b", "c", "d", "leaf")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert DEEP_LEAF_MARKER in out


def test_deep_tree_help_shows_nesting() -> None:
    """zush deep --help shows subcommand 'a'; zush deep a --help shows 'b'; etc."""
    result = _run_zush("deep", "--help")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "a" in out
    result2 = _run_zush("deep", "a", "--help")
    assert result2.returncode == 0
    assert "b" in (result2.stdout + result2.stderr)
    result3 = _run_zush("deep", "a", "b", "c", "d", "--help")
    assert result3.returncode == 0
    assert "leaf" in (result3.stdout + result3.stderr)


# --- Appending under another plugin's group ---


def test_shared_group_command_from_first_plugin() -> None:
    """'shared' group is created by zush_demo; zush shared hello runs demo's command."""
    result = _run_zush("shared", "hello")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert SHARED_HELLO_MARKER in out


def test_shared_appended_command_from_other_plugin() -> None:
    """zush_deep_demo appends under 'shared'; zush shared nested from deep run runs deep_demo's command."""
    result = _run_zush("shared", "nested", "from", "deep", "run")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert SHARED_APPENDED_MARKER in out


def test_self_map_shows_shared_with_both_plugin_branches() -> None:
    """self map shows shared with both hello (demo) and nested/from/deep/run (deep_demo)."""
    result = _run_zush("self", "map")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "shared" in out
    assert "hello" in out
    assert "nested" in out
    assert "run" in out
