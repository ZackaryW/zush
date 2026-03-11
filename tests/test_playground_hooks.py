"""Verify hook behavior by running the zush CLI (subprocess) against the playground."""

import subprocess
from pathlib import Path

import pytest

# Playground path (repo root from test file)
REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYGROUND = REPO_ROOT / "playground"
HOOK_MARKER = "ZUSH_HOOK"


def _run_zush(*args: str) -> subprocess.CompletedProcess:
    """Run zush via uv (uses project env); --mock-path playground then args."""
    cmd = ["uv", "run", "zush", "--mock-path", str(PLAYGROUND)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=15,
    )


def test_hooks_before_and_after_run() -> None:
    """hooks.run: before_cmd and after_cmd both fire (command completes successfully)."""
    result = _run_zush("hooks", "run")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert f"{HOOK_MARKER} before_cmd" in out
    assert f"{HOOK_MARKER} after_cmd" in out
    assert "hooks.run completed" in out


def test_hooks_on_error_fires() -> None:
    """hooks.raise: before_cmd fires, then on_error fires (command raises ValueError)."""
    result = _run_zush("hooks", "raise")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert f"{HOOK_MARKER} before_cmd" in out
    assert f"{HOOK_MARKER} on_error" in out
    assert "ValueError" in out
    assert "intentional error" in out


def test_hooks_on_ctx_match_fires() -> None:
    """hooks.setctx: setting ctx.obj['trigger']=True fires on_ctx_match."""
    result = _run_zush("hooks", "setctx")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert f"{HOOK_MARKER} on_ctx_match" in out
    assert "hooks.setctx completed" in out
