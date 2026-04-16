---
name: create-zush-plugin
description: >
  Guides the agent to scaffold a new zush plugin for this project, including package layout,
  __zush__.py, use of zush.plugin.Plugin, config/env considerations, and basic verification
  via --mock-path or include_current_env. Use when the user asks to create or extend a zush
  plugin. Do not use this skill as the primary guide for remote registry, installer, or
  extension-management packages.
---

# Create zush Plugin

## Purpose

This skill helps the agent create a **new zush plugin** that integrates correctly with the
current zush project. It covers:

- Package layout for a plugin (directory, __init__.py, __zush__.py).
- Using `zush.plugin.Plugin` to define commands with dotted paths.
- How the plugin will be discovered (envs, env_prefix, playground, include_current_env).
- How to verify the plugin using `--mock-path` or the current env.

This skill is for extensions that zush will discover and load from local package roots.
It is **not** the main guide for building a separate extension-management package that owns:

- remote registry access
- GitHub organization or private repository resolution
- install, update, uninstall, or status state
- manager-owned install metadata

For that kind of package, follow `docs/extension-management.md` and use controlled
`self` commands only as the integration surface into zush.

Primary expectation:

- Create a real plugin package with `__zush__.py` in the target env root.
- When migrating an existing installed package into zush, put `__zush__.py` inside that installed package if that package name is what will match `env_prefix` in the real environment.
- Do **not** invent a second sibling plugin package name unless the user explicitly asks for a separate distribution and packaging/update steps are part of the task.
- Do **not** default to placing user implementation in `zush/playground/` unless the user explicitly asks for a playground-only example or demo.
- Use playground only for examples, temporary experiments, or zush-repo-local demos.

## When to Use

The agent should apply this skill when:

- The user asks to **create a new zush “shell” or plugin**.
- The user wants to **add commands/groups** to zush from a separate package.
- The user mentions **`__zush__.py`**, **`ZushPlugin`**, or **`zush.plugin.Plugin`** and wants help scaffolding code.

Do **not** use this skill for generic Click apps; it is specific to this zush repo.

Do **not** use this skill as the main plan when the user is trying to build:

- a package manager for zush extensions
- remote registry support
- GitHub-backed install or update flows
- manager-owned `self install`, `self update`, `self uninstall`, `self search`, or `self status`

In those cases, treat the work as a separate management-extension package and follow
`docs/extension-management.md` first.

## Prerequisites (what the agent should know)

- This repo’s zush architecture:
  - Plugins live in env paths under the configured `env_prefix` (default `"zush_"`).
  - Each plugin package exports an instance with a `.commands` dict in `__zush__.py`.
  - Discovery works on the installed package directory name, not the distribution name and not a package that only exists in the workspace source tree.
  - Commands are registered via **dotted keys** (e.g. `"demo.greet"`, `"shared.hello"`).
  - `zush.plugin.Plugin` is the preferred helper for building `.commands`.
  - Controlled commands under `self` should use the dedicated self-command surface, not ordinary dotted `self.*` command keys.
- How discovery works:
  - Reads `~/.zush/config.toml` (`envs`, `playground`, `env_prefix`, `include_current_env`).
  - If `include_current_env` is true, it also scans the current interpreter’s site-packages
    via `zush.envs.current_site_package_dirs()`.
  - `--mock-path <dir>` temporarily overrides discovery to scan only that dir and disables cache.

## Workflow

When creating a new zush plugin, follow this workflow.

### 1. Clarify requirements

1. Ask (or infer) the following:
   - **Plugin name** (package name). Prefer a name that matches the current `env_prefix`,
     e.g. `zush_<something>`.
   - **Where it should live**:
     - In the target package/env root as a real plugin package, or
     - Inside this repo under `playground/` only if the user explicitly wants a playground example.
   - **Desired commands and groups**:
     - Top-level command/group name(s) (e.g. `demo`, `tools`, `shared`).
     - Subcommands and depth (e.g. `demo greet`, `deep a b c d leaf`).
   - Whether they want **hooks** (before_cmd/after_cmd/on_error/on_ctx_match) as part of this plugin.

2. Check whether the request is actually for a management extension instead of a normal plugin.

Treat it as a management-extension request if the user primarily wants:

- install or uninstall behavior
- search or registry resolution
- GitHub repository or organization lookup
- private source authentication
- manager-owned status or update reporting

If so, do not keep following this skill as the main implementation plan. Switch to the
separate-package guidance in `docs/extension-management.md`.

3. Summarize the intended command tree, e.g.:

   - `zush demo greet`
   - `zush tools convert image`

### 2. Choose env strategy

Depending on the user’s context:

- **Real plugin package in an env root (default)**:
  - Place the plugin in the actual installed package directory that zush will scan.
  - If the user is migrating an existing package and the configured prefix matches that package name, add `__zush__.py` to that package instead of creating a second sibling package.
  - Only create a distinct plugin package such as `zush_<name>/` when the user explicitly wants a separate plugin distribution and you also update packaging so that package is installed in the scanned env.
  - Prefer this when the request is to implement or migrate a real plugin, not just demo one.
  - Verify with `uv run zush --mock-path <env-root> ...` before relying on config changes.

- **Playground-based plugin (demo/example only)**:
  - Place the plugin under `playground/` as `playground/zush_<name>/`.
  - Use this only when the user explicitly wants a playground example, a throwaway demo, or asks to work inside the zush repo playground.

- **Installed plugin in current env**:
  - Place the package somewhere that will be **installed into the uv env** (e.g. via editable install) or otherwise reachable from site-packages.
  - Ensure config has either:
    - `include_current_env = true`, or
    - An `envs` entry that points at the directory containing this package.

Explain briefly which option you’re choosing and why.

Before finishing, verify these four values line up in the real environment:

1. The scanned directory in `envs` or `include_current_env`.
2. The actual installed package directory name under that env.
3. One of the configured `env_prefix` values.
4. The presence of `__zush__.py` in that installed package directory.

### 3. Scaffold the package

Create the following layout for the plugin package (paths relative to the chosen env root):

```text
zush_<name>/
├── __init__.py    # can be empty or minimal
└── __zush__.py    # plugin entry point for zush
```

#### 3.1 `__init__.py`

Use a minimal file, e.g.:

```python
__all__ = []
```

or leave it empty.

#### 3.2 `__zush__.py` with Plugin helper

Use `zush.plugin.Plugin` to define commands. Example pattern:

```python
import click

from zush.plugin import Plugin


def _greet_cb() -> None:
    click.echo("Hello from my zush plugin!")


p = Plugin()

# Top-level group "demo" with a single command "greet"
p.group("demo", help="Demo plugin commands").command(
    "greet",
    callback=_greet_cb,
    help="Say hello from this plugin",
)

ZushPlugin = p  # zush loader looks for an instance with .commands
```

Guidelines:

- Use **`group(...).command(...)`** chaining to build nested commands.
- Use **dotted paths** implicitly via the helper:
  - `p.group("demo").command("greet", ...)` → keys `"demo"` and `"demo.greet"`.
- For controlled commands that should live directly under `self`, use `Plugin.system_command(...)` instead of ordinary dotted keys under `self.*`.
- To attach under another plugin’s group (e.g. shared groups), use the same path:
  - In your plugin: `p.group("shared", ...)` (if you are first) or add deeper commands:
    - `p.group("shared", ...).group("nested").group("from").group("deep").command("run", ...)`

If the user needs hooks:

- In addition to `.commands`, define attributes on the plugin instance:
  - `before_cmd`: list of `(pattern, callback)` for before hooks.
  - `after_cmd`: list of `(pattern, callback)` for after hooks.
  - `on_error`: list of `(ExceptionType, callback)` pairs.
  - `on_ctx_match`: list of `(key, value, callback)` for ZushCtx triggers.
- Make sure the instance you export (`ZushPlugin`) has these attributes; the core
  code will register them.

### 4. Wire into discovery

Depending on the chosen env strategy:

- **Real env root via `--mock-path`**:
  - Place the package in its real env root.
  - Run commands via:

    ```bash
    uv run zush --mock-path /path/to/env-root self map
    uv run zush --mock-path /path/to/env-root <group> <command> ...
    ```

- **Playground**:
  - Place the package under `playground/` in this repo.
  - Run commands via:

    ```bash
    uv run zush --mock-path ./playground <group> <command> ...
    ```

- **Current env (site-packages)**:
  - Ensure the plugin package is importable in the uv-managed env (e.g. via
    editable install).
  - In `~/.zush/config.toml`:

    ```toml
    env_prefix = ["zush_"]           # or include your custom prefix
    include_current_env = true       # scan current interpreter site-packages
    # Optionally: envs = ["/extra/env/path"] if needed
    ```

- **Explicit envs**:
  - If the plugin is on disk outside site-packages, point `envs` at that root:

    ```toml
    envs = ["/path/to/my/env-root"]
    env_prefix = ["zush_"]
    include_current_env = false
    ```

### 5. Verify the plugin

Use at least one of these flows:

#### 5.1 Via `--mock-path`

```bash
uv run zush --mock-path /path/to/env-root self map
uv run zush --mock-path /path/to/env-root <group> <command> ...
```

- Confirm the plugin’s group/command names appear in `self map`.
- Run the new command(s) and assert expected output.

#### 5.2 Via config + include_current_env

After configuring `include_current_env = true` and ensuring the plugin is in site-packages:

```bash
uv run zush self map
uv run zush <group> <command> ...
```

Again, confirm presence in the tree and correct behavior.

### 6. Example: plugin in a real package root

When the user is implementing a real plugin package:

1. If the migrated package itself is the thing zush should discover, create `src/example_pkg/__zush__.py` inside that package.
2. Only use `src/zush_example/__init__.py` and `src/zush_example/__zush__.py` when the user explicitly wants a separate plugin package and the packaging is updated to install it.
3. In `__zush__.py`, use the `Plugin` helper to define the command tree.
4. Verify with:

  ```bash
  uv run zush --mock-path ./src self map
  uv run zush --mock-path ./src example hello
  ```

5. Only add config-based discovery after the `--mock-path` flow is working.

### 7. Example: plugin in this repo’s playground

When the user wants a quick example in this repo:

1. Create `playground/zush_example/__init__.py` and `playground/zush_example/__zush__.py`.
2. In `__zush__.py`, use the `Plugin` helper as shown above to define:
   - `example` group.
   - `example hello` command that prints a recognizable marker.
3. Verify with:

   ```bash
   uv run zush --mock-path ./playground self map
   uv run zush --mock-path ./playground example hello
   ```

4. Optionally, add a small test in `tests/` (following `tests/test_playground_*` patterns)
   that uses subprocess to call zush and assert the marker appears in output.

## Notes and Best Practices

- Prefer **`zush.plugin.Plugin`** over manually building `.commands` dicts; it keeps
  the plugin code consistent with the rest of the project (see `playground/zush_demo`).
- If the feature looks like package management, registry search, remote install, or GitHub source resolution, stop treating it as a normal plugin-scaffold task and follow `docs/extension-management.md` instead.
- If the user asks to create or migrate a real plugin, create `__zush__.py` in the actual installed target package first. Do not substitute a playground implementation or invent a sibling package name unless the task explicitly includes packaging changes for that sibling package.
- Keep plugin callback functions small and focused; avoid heavy logic in `__zush__.py`.
- When appending under shared groups, be mindful of **first-wins** behavior in
  `merge_commands_into_group`: the first plugin to register a given path "owns" the node;
  other plugins can still attach deeper commands under that path.

