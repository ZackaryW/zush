# Plugins

zush plugins are Python packages that export a plugin instance from __zush__.py.

## Minimal Plugin

```python
import click


class Plugin:
    def __init__(self) -> None:
        self.commands = {
            "hello": click.Command("hello", callback=lambda: click.echo("Hello")),
        }


ZushPlugin = Plugin()
```

Command keys may use dotted paths to build nested subcommands, for example:

- demo.greet
- tools.convert.json

## Plugin Helper API

Use zush.pluginloader.plugin.Plugin when you do not want to build dotted paths manually.

```python
import click
from zush.pluginloader.plugin import Plugin


p = Plugin()
p.group("hello", help="Greeting commands").command(
    "say",
    callback=lambda: click.echo("Hi"),
    help="Say hi",
)

ZushPlugin = p
```

## Controlled self Commands

Plugins cannot publish normal self.* command paths.

To add commands under self, use system_command:

```python
import click
from zush.pluginloader.plugin import Plugin


def doctor() -> None:
    click.echo("plugin diagnostics")


p = Plugin()
p.system_command("doctor", callback=doctor, help="Plugin diagnostics")
ZushPlugin = p
```

## Optional Hooks

Plugins may expose these optional attributes on the exported instance:

- before_cmd
- after_cmd
- on_error
- on_ctx_match

These are lifecycle hooks for command execution and shared context changes. They are not CLI commands.

## Persisted Plugin State

Helper-based plugins can persist state with persistedCtx().

```python
import click
from zush.pluginloader.plugin import Plugin


@click.command("save")
def save_cmd() -> None:
    with ZushPlugin.persistedCtx() as state:
        state["count"] = state.get("count", 0) + 1
    click.echo("saved")


p = Plugin()
p.group("persist").command("save", callback=save_cmd.callback)
ZushPlugin = p
```

Supported payload types:

- persistedCtx() for JSON
- persistedCtx("notes.txt") for plain text
- persistedCtx("settings.toml") for TOML
- persistedCtx("settings.yaml") for YAML
