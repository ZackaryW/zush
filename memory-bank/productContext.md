# Product Context: zush

## Why this project exists

zush provides a **single entry point** (`zush`) that discovers and runs plugin-defined commands from multiple environments (folder paths, Python site-packages). Users and third parties can add "shells" without modifying core code.

## Problems it solves

- **Avoid hard-coding shells**: Commands are discovered from configured envs via prefix and `__zush__.py`, not baked into the binary.
- **Support user/third-party plugins**: Any package matching `env_prefix` (e.g. `zush_`) with a valid `__zush__.py` and `ZushPlugin` is loaded and registered.
- **Fast startup**: Caching (`cache.json`) and change detection (`sentry.json`) allow skipping re-parsing envs when nothing has changed.
- **Extensibility and lifecycle hooks**: ZushCtx and hooks (beforeCmd, afterCmd, onError, onCtxMatch) let plugins and core react to command execution and context changes.

## How it should work

- User runs `zush <subcommand...>` where subcommands are defined by plugins (e.g. `zush some one is wrong`).
- Config, cache, and sentry live under `~/.zush/`. Optional: use `zush --mock-path <path> ...` to run with a single env and no caching, without editing config.
- Plugins are loaded from envs (or from `--mock-path`); their Click groups/commands are merged (first-wins); the reserved **`self`** group is added with **`self map`** to print the command tree.
- Hooks are inferred from plugin instance type and run at the appropriate points in the lifecycle.

## User experience goals

- One command (`zush`) for all plugin commands.
- Simple config (envs, optional playground, env_prefix in `config.toml`); or no config edit via `--mock-path`.
- Reserved **`self map`** to inspect the command tree.
- Predictable behavior: regex patterns for beforeCmd/afterCmd, equality for onCtxMatch, instance-type-based hook registration.
