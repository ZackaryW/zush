"""Playground plugin that demonstrates hook behavior.

Hooks are not commands. They are set up by defining on the plugin instance:
  - before_cmd, after_cmd, on_error, on_ctx_match  (lists of (pattern/type, callback))
The core discovers these and registers them with HookRegistry / ZushCtx; they run
around command execution but are never exposed as CLI commands.

The "hooks" group and its commands (run, raise, setctx) exist only to demonstrate
those hooks: they are normal commands that trigger the registered callbacks when run.
"""

import re
import click


# Markers written to stdout so run-based tests can verify hook execution
HOOK_MARKER = "ZUSH_HOOK"


def _before(path: str) -> None:
    click.echo(f"{HOOK_MARKER} before_cmd {path}")


def _after(path: str) -> None:
    click.echo(f"{HOOK_MARKER} after_cmd {path}")


def _on_error(exc: BaseException) -> None:
    click.echo(f"{HOOK_MARKER} on_error {type(exc).__name__} {exc!s}")


def _on_ctx_match() -> None:
    click.echo(f"{HOOK_MARKER} on_ctx_match triggered")
    ctx = click.get_current_context()
    if getattr(ctx, "obj", None) is not None:
        ctx.obj["_on_ctx_match_ran"] = True


class ZushPlugin:
    def __init__(self) -> None:
        # Demo-only commands (not hooks): they exist so we have something to run
        # that triggers the registered before_cmd / after_cmd / on_error / on_ctx_match.
        self.commands = {
            "hooks": click.Group("hooks", help="Demo commands that trigger hook callbacks"),
        }
        # run = normal run; raise = raises; setctx = sets ctx so on_ctx_match fires
        self.commands["hooks.run"] = click.Command(
            "run",
            callback=_run_cb,
            help="Run normally; before_cmd and after_cmd fire",
        )
        self.commands["hooks.raise"] = click.Command(
            "raise",
            callback=_raise_cb,
            help="Raise ValueError; on_error fires",
        )
        self.commands["hooks.setctx"] = click.Command(
            "setctx",
            callback=_setctx_cb,
            help="Set ctx.obj['trigger']=True; on_ctx_match fires",
        )

        # Actual hook registration (never exposed as commands; core registers these at load).
        self.before_cmd = [
            (re.compile(r"^hooks\.(run|raise|setctx)$"), _before),
        ]
        self.after_cmd = [
            (re.compile(r"^hooks\.run$"), _after),  # only run completes successfully
        ]
        self.on_error = [
            (ValueError, _on_error),
        ]
        self.on_ctx_match = [
            ("trigger", True, _on_ctx_match),
        ]


def _run_cb() -> None:
    click.echo("hooks.run completed")


def _raise_cb() -> None:
    raise ValueError("hooks.raise intentional error")


@click.pass_context
def _setctx_cb(ctx: click.Context) -> None:
    # Use ctx.obj (inherited from parent sub_ctx.obj set by ZushGroup) so we see the same ZushCtx
    obj = getattr(ctx, "obj", None)
    if obj is not None:
        obj["trigger"] = True  # triggers on_ctx_match synchronously (callback echoes marker)
    click.echo("hooks.setctx completed (on_ctx_match should have fired)")


ZushPlugin = ZushPlugin()
