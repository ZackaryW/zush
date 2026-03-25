# zush

zush is a Python CLI framework for discovering and serving nested command trees from plugin packages.

It is useful when you want one entry point that can load commands from multiple environments without hard-coding every command into a single application.

## What zush does

- Discovers plugin packages from configured directories or site-packages.
- Exposes plugin commands as nested Click subcommands.
- Provides built-in commands for inspecting the active command tree.
- Supports lightweight plugin hooks and shared runtime context.
- Can be used as a standalone CLI or mounted inside another Click app.

## Requirements

- Python 3.12+
- [Click](https://click.palletsprojects.com/) 8+

## Installation

From the repository:

```bash
uv sync
uv run zush --help
```

Or install it as a package and use the `zush` console script.

## Quick Start

Show the active command tree:

```bash
zush self map
```

Run a discovered plugin command:

```bash
zush <group> <command> ...
```

Use the bundled playground without touching your config:

```bash
uv run zush --mock-path ./playground self map
uv run zush --mock-path ./playground demo greet
```

`--mock-path` and `-m` scan only the given directory and disable cache usage for that run.

## Configuration

zush reads its config from `~/.zush/config.toml`.

If the file does not exist yet, zush creates a bootstrap config on first run.

Supported keys:

| Key | Meaning |
|---|---|
| `envs` | Directories to scan for plugin packages. |
| `env_prefix` | Allowed package name prefixes. Default: `["zush_"]`. |
| `playground` | Optional directory scanned first for local development overrides. |
| `include_current_env` | When `true`, also scan the current Python environment's site-packages. |

Example:

```toml
envs = ["/path/to/plugins", "/another/path"]
env_prefix = ["zush_", "my_"]
playground = "/path/to/zush/playground"
include_current_env = true
```

zush stores config, cache, and other runtime files under `~/.zush/` by default.

## Plugin Layout

zush discovers directories whose names match one of the configured prefixes and that contain `__zush__.py` at the package root.

Inside `__zush__.py`, export a plugin instance with a `.commands` dictionary.

Minimal example:

```python
import click


class Plugin:
    def __init__(self) -> None:
        self.commands = {
            "hello": click.Command("hello", callback=lambda: click.echo("Hello")),
        }


ZushPlugin = Plugin()
```

Command keys may use dotted paths to build nested subcommands:

- `demo.greet`
- `tools.convert.json`

## Plugin Helper API

If you do not want to manage dotted command paths by hand, use `zush.plugin.Plugin`:

```python
import click
from zush.plugin import Plugin


p = Plugin()
p.group("hello", help="Greeting commands").command(
    "say",
    callback=lambda: click.echo("Hi"),
    help="Say hi",
)

ZushPlugin = p
```

## Plugin Hooks

Plugins may optionally expose these attributes on the exported instance:

- `before_cmd`
- `after_cmd`
- `on_error`
- `on_ctx_match`

These are lifecycle hooks for command execution and shared context changes. They are not exposed as CLI commands.

## Persisted Plugin State

Helper-based plugins can persist state with `persistedCtx()`:

```python
import click
from zush.plugin import Plugin


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

- `persistedCtx()` for JSON
- `persistedCtx("notes.txt")` for plain text
- `persistedCtx("settings.toml")` for TOML
- `persistedCtx("settings.yaml")` for YAML

## Built-in Commands

The `self` group is reserved for zush itself.

- `zush self map` prints the active command tree.
- `zush self config` opens the active zush config directory.

Plugins cannot register commands under `self`.

## Embedding

zush can be mounted as a subcommand group inside another Click application:

```python
from pathlib import Path

import click

from zush import create_zush_group
from zush.config import Config
from zush.paths import DirectoryStorage, temporary_storage


app = click.Group("myapp")

app.add_command(create_zush_group(), "zush")

storage = DirectoryStorage(Path("/myapp/data/zush"))
config = Config(envs=[Path("/my/envs")], env_prefix=["zush_"])
app.add_command(create_zush_group(config=config, storage=storage), "zush")

with temporary_storage() as temp_storage:
    app.add_command(create_zush_group(config=config, storage=temp_storage), "temp-zush")
```

Factory signature:

```python
create_zush_group(name="zush", config=None, storage=None, mock_path=None)
```

## Playground

The `playground/` directory contains sample plugins for local testing and exploration.

See [playground/README.md](playground/README.md) for examples.

## Development

Install dev dependencies and run tests:

```bash
uv sync --extra dev
uv run pytest
```
