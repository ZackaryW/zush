# zush

zush is a Python CLI framework for discovering and serving nested command trees from plugin packages.

It is useful when you want one entry point that can load commands from multiple environments without hard-coding every command into a single application.

## What zush does

- Discovers plugin packages from configured directories or site-packages.
- Exposes plugin commands as nested Click subcommands.
- Provides built-in commands for inspecting the active command tree.
- Supports lightweight plugin hooks and shared runtime context.
- Can be used as a standalone CLI or mounted inside another Click app.

## Current Capabilities

zush currently provides:

- local extension discovery from configured env roots and optional current site-packages
- ordered discovery-provider selection for local source layouts
- plugin loading from package-local `__zush__.py`
- extension enable or disable control through `disabled_extensions` and `zush self toggle`
- boot-time diagnostics through `zush self diagnostics`
- controlled `self` command registration for plugins and host apps
- built-in cron scheduling with reusable registrations, lifejobs, and simulated runtime controls
- detached service management and runtime provider integration

zush does not currently act as a package manager. Remote registry lookup, GitHub-based installation, update policy, and install metadata are better implemented in a separate extension-management package.

See [docs/extension-management.md](docs/extension-management.md) for the recommended architecture.

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

Open the active zush config directory:

```bash
zush self config
```

Show collected discovery and command-registration diagnostics:

```bash
zush self diagnostics
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
| `disabled_extensions` | Optional list of extension keys to skip during discovery. |

Example:

```toml
envs = ["/path/to/plugins", "/another/path"]
env_prefix = ["zush_", "my_"]
playground = "/path/to/zush/playground"
include_current_env = true
disabled_extensions = ["zush_demo"]
```

zush stores config, cache, and other runtime files under `~/.zush/` by default.
On Windows, `zush self config` now uses the native directory opener and surfaces a CLI error if the folder cannot be opened.

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

If you do not want to manage dotted command paths by hand, use `zush.pluginloader.plugin.Plugin`:

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

Helper-based plugins can also register controlled commands directly under `self`:

```python
import click
from zush.pluginloader.plugin import Plugin


def doctor() -> None:
    click.echo("plugin diagnostics")


p = Plugin()
p.system_command("doctor", callback=doctor, help="Plugin diagnostics")
ZushPlugin = p
```

These commands are mounted under `zush self ...` without treating ordinary `self.*` dotted command keys as part of the normal plugin command tree.

## Plugin Hooks

Plugins may optionally expose these attributes on the exported instance:

- `before_cmd`
- `after_cmd`
- `on_error`
- `on_ctx_match`

These are lifecycle hooks for command execution and shared context changes. They are not exposed as CLI commands.

## Runtime Globals

zush also provides a process-local runtime object store at `zush.core.runtime.g`.

This is useful for sharing live objects during a single zush process, for example:

- schedulers
- clients
- registries
- in-memory service handles

Helper-based plugins can register objects into that store:

```python
from zush.pluginloader.plugin import Plugin


p = Plugin()
p.provide("scheduler", object())
ZushPlugin = p
```

If the object should be created lazily, use `provide_factory(...)` instead. The value is materialized on first access through `zush.core.runtime.g` and then cached for the rest of the process:

```python
from zush.pluginloader.plugin import Plugin


def build_scheduler():
    return object()


p = Plugin()
p.provide_factory("scheduler", build_scheduler)
ZushPlugin = p
```

Factories may also accept a plugin runtime object as their first argument. That runtime can start, stop, restart, or ensure readiness for services declared by the same plugin.

When the provider depends on a service, declare that dependency directly so zush can ensure readiness before construction and invalidate the cached provider when the service changes:

```python
from zush.pluginloader.plugin import Plugin


def build_client(runtime):
    return MyClient(runtime)


def close_client(client):
    client.close()


p = Plugin()
p.provide_factory(
    "client",
    build_client,
    service="web",
    recreate_on_restart=True,
    teardown=close_client,
)
ZushPlugin = p
```

With that setup:

- zush ensures `web` is ready before the provider is first created
- the provider is rebuilt after `web` restarts or stops
- the previous provider instance is passed to `teardown` before replacement

The runtime object passed to factories can also be used directly from plugin commands when you want plugin-facing lifecycle controls instead of only relying on `self services`:

```python
@click.command("restart")
def restart_cmd():
    click.echo(ZushPlugin.runtime.restart_service("web"))
```

Objects in `zush.core.runtime.g` are not persisted to disk and are only available for the current process.

## Persisted Plugin State

Helper-based plugins can persist state with `persistedCtx()`:

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

- `persistedCtx()` for JSON
- `persistedCtx("notes.txt")` for plain text
- `persistedCtx("settings.toml")` for TOML
- `persistedCtx("settings.yaml")` for YAML

## Detached Services

Plugins can also declare detached subprocess-backed services for zush to manage.

Helper-based example:

```python
import sys

from zush.pluginloader.plugin import Plugin


p = Plugin()
p.service(
    "web",
    [sys.executable, "-m", "flask", "run"],
    auto_restart=True,
)

ZushPlugin = p
```

zush persists service registration and state in user data and exposes a built-in control surface:

```bash
zush self services web --start
zush self services web --status
zush self services web --restart
zush self services web --stop
```

If a service is marked `auto_restart=True`, zush can restart it when it is missing or when its health check reports unhealthy.

Services may also supply a custom control interface when subprocess spawning is not the only or best lifecycle mechanism. A control interface can implement `start(runtime)`, `stop(runtime)`, `restart(runtime)`, and `status(runtime)`. When present, zush uses those methods first and falls back to OS-level termination only when `terminate_fallback=True`.

Example:

```python
from zush.pluginloader.plugin import Plugin


class Control:
    def start(self, runtime):
        runtime.state["running"] = True
        runtime.save()
        return "started web"

    def stop(self, runtime):
        runtime.state["running"] = False
        runtime.save()
        return "stopped web"

    def status(self, runtime):
        return "healthy" if runtime.state.get("running") else "stopped"


p = Plugin()
p.service(
    "web",
    ["python", "app.py"],
    control=Control(),
    terminate_fallback=True,
)
ZushPlugin = p
```

This makes it possible for one plugin package to own both a provider object and the server/service it depends on.

The playground contains a concrete example in [playground/README.md](playground/README.md) under `zush_provider_service_demo`.

Health checks can be provided as callbacks that return either:

- `True` or `False`
- `(True, "message")` or `(False, "message")`

Example:

```python
import httpx
import sys

from zush.pluginloader.plugin import Plugin


def healthcheck(_state):
    try:
        response = httpx.get("http://127.0.0.1:5000/health", timeout=0.5)
        return response.status_code == 200, f"status={response.status_code}"
    except Exception as exc:
        return False, str(exc)


p = Plugin()
p.service(
    "web",
    [sys.executable, "-m", "flask", "run", "--no-reload"],
    auto_restart=True,
    healthcheck=healthcheck,
)
```

The test suite includes end-to-end service coverage with a real Flask subprocess and `httpx` clients, including restart behavior for unhealthy services.

Combined with `provide_factory(...)`, this lets a single plugin package own:

- the service declaration
- the lifecycle control interface
- the provider/control-surface object
- the plugin-facing commands that use both

## Cron Scheduling

zush includes a built-in scheduler under `zush self cron ...`.

Cron configuration is stored in the active zush config directory in `cron.json`. Single-day completion tracking is stored separately in `cron_completion.jsonl` when you opt a job or lifejob into that behavior.

The scheduler uses a two-phase model:

1. Register one reusable command payload.
2. Add one or more cron jobs that reference that registration.

Basic flow:

```bash
zush self cron register nightly-task demo.run region=west
zush self cron add nightly-task "0 2 * * *"
zush self cron list
```

Registrations keep the actual command path and its stored args or kwargs. Jobs only keep the schedule plus the registration name, so multiple schedules can reuse the same registered command.

Trailing tokens after `register <name> <command_path>` are stored as command input:

- plain trailing tokens become positional args
- `key=value` tokens become keyword args

Example:

```bash
zush self cron register report-task reports.build weekly region=west count=3
```

Detached execution is configured on the registration, not on the job. Append `-d` or `--detach` to the end of the register command if matching jobs should run in a detached worker process:

```bash
zush self cron register nightly-task demo.run --detach
zush self cron add nightly-task "0 2 * * *"
```

If a registration is detached, any cron job or lifejob that points at it inherits that detached behavior.

### Lifejobs

Lifejobs are delayed follower jobs attached to a normal cron job. They reuse a registration and run some number of seconds after the target job finishes.

Example:

```bash
zush self cron register main-task demo.main
zush self cron register cleanup-task demo.cleanup
zush self cron add main-task "*/5 * * * *"
zush self cron add cleanup-task --lifejob cron-1 --delay 30
```

This creates a normal scheduled job for `main-task`, then a lifejob that runs `cleanup-task` 30 seconds after `cron-1` completes. If the target job runs again before the lifejob fires, zush reschedules the lifejob from the latest target run.

Removing a cron job also removes any attached lifejobs.

### Single-Day Completion

Use `-sdc` or `--single-day-complete` when a job or lifejob should run at most once per day even if it becomes due multiple times:

```bash
zush self cron add nightly-task "*/5 * * * *" --single-day-complete
zush self cron add cleanup-task --lifejob cron-1 --delay 30 --single-day-complete
```

When enabled, zush records the completed entry name under that ISO date in `cron_completion.jsonl` and skips later same-day due runs for that entry.

By default, the completion day rolls over at `00:00`. Use `--day-change HH:MM` to move that boundary when a logical workday should reset later, such as `06:00`:

```bash
zush self cron add nightly-task "*/5 * * * *" --single-day-complete --day-change 06:00
zush self cron add cleanup-task --lifejob cron-1 --delay 30 --single-day-complete --day-change 06:00
```

With `--day-change 06:00`, a run at `2026-04-17T05:30:00` still counts toward the `2026-04-16` completion day, while runs at or after `06:00` count toward `2026-04-17`.

### Runtime Controls

Use `zush self cron start` to run the foreground scheduler loop:

```bash
zush self cron start
```

The start surface also supports simulation and testing controls:

```bash
zush self cron start --scale 60 --mocktime 2026-04-17T10:15:00 --dry-run
```

- `--scale` advances simulated scheduler time faster or slower than wall clock
- `--mocktime` starts the scheduler from a fixed ISO datetime
- `--dry-run` evaluates due jobs and lifejobs without executing commands or persisting cron state changes

Use `zush self cron register --help`, `zush self cron add --help`, and `zush self cron start --help` for the full flag descriptions.

## Built-in Commands

The `self` group is reserved for zush itself.

- `zush self map` prints the active command tree.
- `zush self config` opens the active zush config directory.
- `zush self diagnostics` prints collected discovery and command-registration diagnostics for the current boot.
- `zush self toggle` shows which extensions are loaded this boot and which are disabled for the next boot.
- `zush self toggle <extension>` enables or disables one extension key for future boots.
- `zush self services ...` manages plugin-declared detached services.
- `zush self cron ...` manages cron registrations, jobs, lifejobs, and scheduler runtime controls.

Plugins cannot publish ordinary command paths under `self.*`.

Plugins may register controlled self commands through `Plugin.system_command(...)`, and host apps may register their own self commands when calling `create_zush_group(...)`. Built-in zush command names still take priority, so plugin or host registrations cannot override `map`, `config`, `diagnostics`, `toggle`, `services`, or `cron`.

## Embedding

zush can be mounted as a subcommand group inside another Click application:

```python
from pathlib import Path

import click

from zush import create_zush_group
from zush.configparse.config import Config
from zush.core.storage import DirectoryStorage
from zush.mocking.storage import temporary_storage


app = click.Group("myapp")

app.add_command(create_zush_group(), "zush")

storage = DirectoryStorage(Path("/myapp/data/zush"))
config = Config(envs=[Path("/my/envs")], env_prefix=["zush_"])
app.add_command(create_zush_group(config=config, storage=storage), "zush")

app.add_command(
    create_zush_group(
        config=config,
        storage=storage,
        system_commands={
            "doctor": click.Command("doctor", callback=lambda: click.echo("host diagnostics")),
        },
    ),
    "zush",
)

with temporary_storage() as temp_storage:
    app.add_command(create_zush_group(config=config, storage=temp_storage), "temp-zush")
```

Factory signature:

```python
create_zush_group(name="zush", config=None, storage=None, mock_path=None, system_commands=None)
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
