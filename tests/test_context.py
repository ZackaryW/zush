"""TDD: context module — ZushCtx (observable dict) and hook registry."""

import re

import pytest

from zush.context import ZushCtx, HookRegistry


def test_zush_ctx_dict_like():
    """ZushCtx behaves like a dict for get/set."""
    ctx = ZushCtx()
    ctx["a"] = 1
    assert ctx["a"] == 1
    assert ctx.get("b", 2) == 2
    ctx["b"] = 3
    assert ctx["b"] == 3


def test_zush_ctx_on_ctx_match_fires_on_set():
    """When a key is set and ctx[key] == expected, callback runs."""
    ctx = ZushCtx()
    seen = []
    ctx.register_on_ctx_match("flag", True, lambda: seen.append(1))
    ctx["flag"] = False
    assert len(seen) == 0
    ctx["flag"] = True
    assert len(seen) == 1
    ctx["flag"] = True
    assert len(seen) == 2


def test_zush_ctx_on_ctx_match_equality():
    """onCtxMatch uses == (so 0 and 0.0 both match expected 0)."""
    ctx = ZushCtx()
    seen = []
    ctx.register_on_ctx_match("x", 0, lambda: seen.append(1))
    ctx["x"] = 0
    assert len(seen) == 1
    ctx["x"] = 0.0
    assert len(seen) == 2


def test_hook_registry_before_cmd_regex():
    """beforeCmd callbacks receive command path; regex match decides if run."""
    reg = HookRegistry()
    seen = []
    reg.register_before_cmd(re.compile(r"^foo\."), lambda path: seen.append(("before", path)))
    reg.run_before_cmd("foo.bar")
    assert seen == [("before", "foo.bar")]
    seen.clear()
    reg.run_before_cmd("other.bar")
    assert seen == []


def test_hook_registry_after_cmd():
    """afterCmd runs for matching pattern."""
    reg = HookRegistry()
    seen = []
    reg.register_after_cmd(re.compile(r"^foo"), lambda path: seen.append(("after", path)))
    reg.run_after_cmd("foo.bar")
    assert seen == [("after", "foo.bar")]


def test_hook_registry_on_error():
    """onError runs when exception type matches."""
    reg = HookRegistry()
    seen = []
    reg.register_on_error(ValueError, lambda exc: seen.append(exc))
    reg.run_on_error(ValueError("x"))
    assert len(seen) == 1 and seen[0].args == ("x",)
    seen.clear()
    reg.run_on_error(TypeError("y"))
    assert len(seen) == 0


def test_hook_registry_on_error_subclass():
    """onError runs for subclass of registered type."""
    reg = HookRegistry()

    class MyErr(ValueError):
        pass

    seen = []
    reg.register_on_error(ValueError, lambda exc: seen.append(exc))
    reg.run_on_error(MyErr("z"))
    assert len(seen) == 1
