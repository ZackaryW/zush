# zush

**Zack's useful shell** — a Click-based CLI that discovers and runs plugin commands from configured environments. One entry point (`zush`) loads plugins and exposes their commands as subcommands, with hooks and a shared context.

## Requirements

- Python 3.12+
- [Click](https://click.palletsprojects.com/) ≥ 8.0

## Installation

```bash
# From the repo (e.g. with uv)
uv sync
uv run zush --help
```

Or install as a package and use the `zush` console script.

## Quick start

```bash
# List commands (built-in tree view)
zush self map

# Run a plugin command (once you have envs configured)
zush <group> <command> ...
```

**Try it without config** — use the repo playground and skip cache:

```bash
uv run zush --mock-path ./playground self map
uv run zush --mock-path ./playground demo greet
```

`--mock-path` / `-m` uses only that directory as the plugin env and disables cache/sentry.

## Config

**Location:** `~/.zush/config.toml`

| Key         | Description |
|------------|-------------|
| `envs`     | List of paths to scan for plugins (folders or site-packages). |
| `env_prefix` | Package name prefix(es), default `["zush_"]`. Only packages whose name starts with one of these are loaded. |
| `playground` | Optional path scanned first (overloaded index); first-wins merge. Good for local dev. |

Example:

```toml
envs = ["/path/to/my/envs", "/another/path"]
env_prefix = ["zush_", "my_"]
playground = "/path/to/zush/playground"   # optional
```

Config, cache, and sentry live under `~/.zush/` by default. When [embedding](#embedding) zush, you can pass a custom storage so config/cache use a different directory.

## Plugins

- **Discovery:** From each env path, zush looks for **directories** whose name starts with one of the `env_prefix` values and that contain **`__zush__.py`** at the root.
- **Contract:** In `__zush__.py`, export a plugin **instance** (e.g. an object with a `.commands` dict). `commands` is `dict[str, click.Command | click.Group]`; keys are dotted paths (e.g. `demo.greet`, `tools.convert`).
- **Hooks (optional):** On the same instance you can define `before_cmd`, `after_cmd`, `on_error`, `on_ctx_match` (lists of patterns/callbacks). These are registered with the core and run around command execution or when the shared context is updated; they are **not** exposed as CLI commands.

Minimal plugin:

```python
# my_env/zush_hello/__zush__.py
import click

class ZushPlugin:
    def __init__(self):
        self.commands = {
            "hello": click.Command("hello", callback=lambda: click.echo("Hello"))
        }

ZushPlugin = ZushPlugin()  # export instance
```

See `playground/zush_demo` and `playground/zush_hooks_demo` for examples.

## Reserved group: `self`

- **`self`** is reserved; plugins cannot register commands under it.
- Built-in command: **`zush self map`** — prints the command tree (like `tree`).

## Embedding

Zush can be used as a **subcommand group** of another Click app, with its own config and storage:

```python
import click
from zush import create_zush_group
from zush.config import Config
from zush.paths import DirectoryStorage
from pathlib import Path

app = click.Group("myapp")

# Default: use ~/.zush for config/cache
app.add_command(create_zush_group(), "zush")

# Custom envs and storage directory
storage = DirectoryStorage(Path("/myapp/data/zush"))
config = Config(envs=[Path("/my/envs")], env_prefix=["zush_"])
app.add_command(create_zush_group(config=config, storage=storage), "zush")
```

Then: `myapp zush self map`, `myapp zush <plugin commands>`, etc.

**Factory signature:** `create_zush_group(name="zush", config=None, storage=None, mock_path=None)`. Omitted `config`/`storage` use default (load from `~/.zush`). `mock_path` overrides envs and disables cache for that run.

## Playground

The **`playground/`** directory contains sample plugins (`zush_demo`, `zush_hooks_demo`). Use `--mock-path ./playground` to run against them without editing config. See `playground/README.md` for details.

## Development

```bash
uv sync --extra dev
uv run pytest
```

Tests live in `tests/`; `pythonpath` is set to `src`.

## Memory bank

Project context and design live in **`memory-bank/`**. Cline (and similar tooling) reads these files at task start as the source of truth for scope, architecture, and current focus.
