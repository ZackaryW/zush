# zush

zush is a Python CLI framework for discovering and serving nested command trees from plugin packages.

It gives you one CLI entry point that can load commands from multiple environments without hard-coding every command into one application.

## What zush does

- Discovers plugin packages from configured directories or site-packages.
- Exposes plugin commands as nested Click subcommands.
- Provides built-in self commands for inspection and operations.
- Supports plugin hooks, persisted plugin state, runtime providers, services, and cron scheduling.
- Can run standalone or be embedded inside another Click app.

## Current capabilities

zush currently provides:

- local extension discovery from configured env roots and optional current site-packages
- ordered discovery-provider selection for local source layouts
- plugin loading from package-local __zush__.py
- extension enable or disable control through disabled_extensions and self toggle
- boot-time diagnostics through self diagnostics
- controlled self command registration for plugins and host apps
- built-in cron scheduling with reusable registrations, lifejobs, and simulated runtime controls
- detached service management and runtime provider integration

zush is not a package manager. Remote registry lookup, GitHub-based installation, update policy, and install metadata are better implemented in a separate extension-management package.

See [docs/extension-management.md](docs/extension-management.md) for that architecture.

## Requirements

- Python 3.12+
- Click 8+

## Installation

From repository source:

```bash
uv sync
uv run zush --help
```

Or install as a package and run the zush console entry point.

## Quick start

Show the active command tree:

```bash
zush self map
```

Open the active zush config directory:

```bash
zush self config
```

Show discovery and registration diagnostics:

```bash
zush self diagnostics
```

Run a discovered plugin command:

```bash
zush <group> <command> ...
```

Use the bundled playground without touching your local config:

```bash
uv run zush --mock-path ./playground self map
uv run zush --mock-path ./playground demo greet
```

## Documentation

Detailed guides now live in the docs folder:

- Configuration: [docs/configuration.md](docs/configuration.md)
- Plugin authoring and helper API: [docs/plugins.md](docs/plugins.md)
- Runtime globals and services: [docs/runtime-and-services.md](docs/runtime-and-services.md)
- Cron scheduling and plugin cron sync: [docs/cron.md](docs/cron.md)
- Embedding zush in host apps: [docs/embedding.md](docs/embedding.md)
- Extension-management architecture: [docs/extension-management.md](docs/extension-management.md)

## Built-in self commands

The self group is reserved for zush core commands:

- self map
- self config
- self diagnostics
- self toggle
- self services
- self cron

Plugins may add controlled self commands through Plugin.system_command(...). Reserved built-in names above cannot be overridden.

## Playground

The playground folder contains sample plugins for local testing and exploration.

See [playground/README.md](playground/README.md).

## Development

Install dev dependencies and run tests:

```bash
uv sync --extra dev
uv run pytest
```
