# Project Brief: zush

## Project

zush is a Python shell that discovers and runs a set of "shells" (plugins) following configured behavior. A single entry point (`zush`) loads plugins from user-configured environments and exposes their commands as subcommands.

## CLI

- **Framework**: Click-based.
- **Custom group**: Uses a **custom group** (not stock `click.Group`) to allow hooks and custom behavior (beforeCmd, afterCmd, onError, onCtxMatch).

## Config

**Location**: `~/.zush/config.toml`

- **envs**: List of paths (folder paths and/or Python site-packages directories) to scan for plugins.
- **playground**: Optional path to an **overloaded index env**. When set, this directory is scanned first; plugins from the playground take precedence (first-wins merge). Use for local testing (e.g. repo `playground/` with packages that simulate plugins).
- **env_prefix**: List of strings, default `["zush_"]`. Used to filter which packages are considered zush plugins (name must match one of the prefixes).

**CLI overload (no config edit)**: `zush --mock-path <path> ...` (or `-m`) uses only that path as the env and **disables caching** (no cache/sentry read or write). Use for testing without touching config.toml.

## Plugin contract

- From each env, discover packages whose name matches the prefix pattern.
- If a package has **`__zush__.py`** at its root, load it and look for an exported **`ZushPlugin`** class.
- Plugin exposes a **dict[str, ClickGroup | ClickCommand]** (e.g. `some.one` = ClickGroup, `is` = ClickCommand). These are registered so the user can run e.g. `zush some one is wrong`.
- The plugin is **initialized with an instance** in `__zush__.py`. When loading, hook registration is inferred **by instance type** (inspect the loaded instance and register hooks based on its type/attributes).

## Reserved group: self

- **`self`** is a reserved group name; plugins cannot register commands under `self` (they are skipped during merge).
- After merging plugin commands, the built-in **`self`** group is added with:
  - **`self map`**: Prints the command tree in a tree-style layout (like the `tree` command).

## ZushCtx and hooks

- **ZushCtx**: Shared context object for the lifetime of a `zush` run, available as a global (or thread-local) instance. Dict-like and observable: assignments are monitored so onCtxMatch hooks can run when conditions become true.
- **beforeCmd(pattern)**: Runs before any command whose path matches the regex pattern.
- **afterCmd(pattern)**: Runs after that command completes successfully.
- **onError(exception_type)**: Runs when an exception of the given type (or subclass) is raised.
- **onCtxMatch("key": value)**: Single-layer condition on ZushCtx; runs immediately when `ctx["key"] == value` becomes true (on set).

## Cache

**Location**: `~/.zush/cache.json`

Nested dict mapping CLI path to instance metadata, e.g.:

```json
{
  "some": {
    "one": {
      "_zushtype": "path",
      "path": "...",
      "exported": ["is.wrong", "..."]
    }
  }
}
```

## Change detection (sentry)

**Location**: `~/.zush/sentry.json`

List of entries per env: `env`, `root` (bool), optional `package`, `last_cached`. Used to skip re-parsing an env when nothing has changed.

Example shape:

```json
[
  { "env": "...", "root": true, "last_cached": "..." },
  { "env": "...", "root": false, "package": "...", "last_cached": "..." }
]
```
