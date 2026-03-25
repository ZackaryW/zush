"""Verify hook behavior by running the zush CLI against copied playground fixtures."""

from tests.playground_helpers import copy_playground, make_subprocess_env, make_test_home, run_zush

HOOK_MARKER = "ZUSH_HOOK"


def _run_zush(tmp_path, *args: str):
    playground = copy_playground(tmp_path, "zush_hooks_demo")
    home = make_test_home()
    return run_zush(playground, *args, env=make_subprocess_env(home=home))


def test_hooks_before_and_after_run(tmp_path) -> None:
    """hooks.run: before_cmd and after_cmd both fire (command completes successfully)."""
    result = _run_zush(tmp_path, "hooks", "run")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert f"{HOOK_MARKER} before_cmd" in out
    assert f"{HOOK_MARKER} after_cmd" in out
    assert "hooks.run completed" in out


def test_hooks_on_error_fires(tmp_path) -> None:
    """hooks.raise: before_cmd fires, then on_error fires (command raises ValueError)."""
    result = _run_zush(tmp_path, "hooks", "raise")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert f"{HOOK_MARKER} before_cmd" in out
    assert f"{HOOK_MARKER} on_error" in out
    assert "ValueError" in out
    assert "intentional error" in out


def test_hooks_on_ctx_match_fires(tmp_path) -> None:
    """hooks.setctx: setting ctx.obj['trigger']=True fires on_ctx_match."""
    result = _run_zush(tmp_path, "hooks", "setctx")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert f"{HOOK_MARKER} on_ctx_match" in out
    assert "hooks.setctx completed" in out
