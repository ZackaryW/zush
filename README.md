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

Normal config-based runs use cache and sentry. If an env has not changed, zush should still rebuild the live command tree from cached package paths; an unchanged env must not collapse the CLI down to `self` only.

## Config

**Location:** `~/.zush/config.toml`

If the config file does not exist, zush now creates a bootstrap config on first run with `include_current_env = true` so plugins installed into the current interpreter are discoverable by default.

| Key         | Description |
|------------|-------------|
| `envs`     | List of paths to scan for plugins (folders or site-packages). |
| `env_prefix` | Package name prefix(es), default `["zush_"]`. Only packages whose name starts with one of these are loaded. |
| `playground` | Optional path scanned first (overloaded index); first-wins merge. Good for local dev. |
| `include_current_env` | Optional boolean; when true, also scan the current interpreter's site-packages (e.g. the uv env running `zush`). |

Example:

```toml
envs = ["/path/to/my/envs", "/another/path"]
env_prefix = ["zush_", "my_"]
playground = "/path/to/zush/playground"   # optional
include_current_env = true                # also scan the env running `zush`
```

Config, cache, and sentry live under `~/.zush/` by default. When [embedding](#embedding) zush, you can pass a custom storage so config/cache use a different directory; include_current_env controls whether the *current* interpreter's site-packages are also scanned.

## Plugins

- **Discovery:** From each env path, zush looks for **directories** whose name starts with one of the `env_prefix` values and that contain **`__zush__.py`** at the root.
- **Contract:** In `__zush__.py`, export a plugin **instance** (e.g. an object with a `.commands` dict). `commands` is `dict[str, click.Command | click.Group]`; keys are dotted paths (e.g. `demo.greet`, `tools.convert`).
- **Hooks (optional):** On the same instance you can define `before_cmd`, `after_cmd`, `on_error`, `on_ctx_match` (lists of patterns/callbacks). These are registered with the core and run around command execution or when the shared context is updated; they are **not** exposed as CLI commands.

**Migration rule:** When migrating an existing package into zush discovery, put `__zush__.py` inside the installed package directory that zush will actually scan. If the package zush is meant to discover is `applewood_letty_chaos_photos`, the plugin entrypoint belongs at `applewood_letty_chaos_photos/__zush__.py` inside that installed package.

**Do not split a migration into a second sibling plugin package by default.** A sibling package such as `zush_applewood_letty_chaos_photos` is only valid when the task explicitly requires a separate distribution and the packaging/install flow is updated to ship that package into the scanned environment.

**Real-world check:** Before assuming discovery is broken, confirm all of the following line up in the same environment:

- The directory listed in `envs` or discovered through `include_current_env`.
- The installed package directory name under that env's `site-packages`.
- A matching `env_prefix` value.
- A `__zush__.py` file inside that installed package directory.

If those line up but `zush` intermittently shows only `self`, the next thing to check is cached discovery behavior: unchanged envs must be rehydrated from cache into the live command tree, not skipped entirely.

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

**Helper (optional):** Use `zush.plugin` for a chainable builder so you don’t manage dotted keys by hand:

```python
# my_env/zush_hello/__zush__.py
import click
from zush.plugin import Plugin

p = Plugin()
p.group("hello", help="Greetings").command("say", callback=lambda: click.echo("Hi"), help="Say hi")
ZushPlugin = p
```

**Persisted plugin config:** Helper-based plugins can persist state with `persistedCtx()`.

```python
import click
from zush.plugin import Plugin

@click.command("save")
def save_cmd():
    with ZushPlugin.persistedCtx() as state:
        state["count"] = state.get("count", 0) + 1
    click.echo("saved")

p = Plugin()
p.group("persist", help="Persisted state demo").command("save", callback=save_cmd.callback)
ZushPlugin = p
```

By default this uses `~/.zush/cfg-index.json` to map the plugin package name to a UUID, then stores payload files under `~/.zush/cfgs/{uuid}/...`.

- `with ZushPlugin.persistedCtx():` uses `zush.json`
- `with ZushPlugin.persistedCtx("notes.txt"):` uses plain text
- `with ZushPlugin.persistedCtx("settings.toml"):` uses TOML
- `with ZushPlugin.persistedCtx("settings.yaml"):` uses YAML

Persistence identity is package-name based. If the same plugin package name appears in multiple scanned envs, they intentionally share the same persisted config.

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
from zush.paths import DirectoryStorage, temporary_storage
from pathlib import Path

app = click.Group("myapp")

# Default: use ~/.zush for config/cache
app.add_command(create_zush_group(), "zush")

# Custom envs and storage directory
storage = DirectoryStorage(Path("/myapp/data/zush"))
config = Config(envs=[Path("/my/envs")], env_prefix=["zush_"])
app.add_command(create_zush_group(config=config, storage=storage), "zush")

# Temporary isolated storage (tests, demos, disposable sessions)
with temporary_storage() as temp_storage:
    app.add_command(create_zush_group(config=config, storage=temp_storage), "temp-zush")
```

Then: `myapp zush self map`, `myapp zush <plugin commands>`, etc.

**Factory signature:** `create_zush_group(name="zush", config=None, storage=None, mock_path=None)`. Omitted `config`/`storage` use default (load from `~/.zush`). `mock_path` overrides envs and disables cache for that run.

If you need an isolated config/cache/cfg-index directory, use `temporary_storage()` from `zush.paths`. It yields a `DirectoryStorage` backed by a temp directory and cleans it up automatically when the context exits.

## Playground

The **`playground/`** directory contains sample plugins (`zush_demo`, `zush_hooks_demo`). Use `--mock-path ./playground` to run against them without editing config. See `playground/README.md` for details.

Playground examples are for demos and local verification only. They are not a substitute for placing `__zush__.py` in the real installed package when the task is a real migration.

## Development

```bash
uv sync --extra dev
uv run pytest
```

Tests live in `tests/`; `pythonpath` is set to `src`.

## Memory bank

Project context and design live in **`memory-bank/`**. Cline (and similar tooling) reads these files at task start as the source of truth for scope, architecture, and current focus.
