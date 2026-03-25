# Progress: zush

## What works

- **Config**: load_config() from ~/.zush/config.toml (envs, env_prefix, optional playground, include_current_env flag).
- **Config bootstrap**: when ~/.zush/config.toml is missing, zush creates a default config file and enables current-env scanning by default.
- **CLI overload**: `--mock-path` / `-m` parsed in main(); single env, no cache.
- **Discovery**: run_discovery() scans envs (or mock_path), loads plugins, merges tree, updates cache/sentry unless no_cache; playground in config scanned first.
- **Cached discovery**: unchanged envs can be rehydrated from cached package paths so the live CLI tree remains complete even when sentry skips a filesystem rescan.
- **Plugin loader**: load_plugin() from __zush__.py; instance with .commands; prefer ZushPlugin.
- **Context**: ZushCtx (observable dict, onCtxMatch on set), HookRegistry (before/after/onError with regex/type).
- **Group**: ZushGroup with hooks, sub_ctx.obj = zush_ctx; merge_commands_into_group (first-wins; skip reserved `self`); add_reserved_self_group (self + map).
- **Reserved self**: Group `self` with command `map` (tree-style command map); plugins cannot register under `self`.
- **Reserved self**: Group `self` with commands `map` and `config`; plugins cannot register under `self`.
- **main()**: argv parse → config → discovery → hooks → build CLI → add self → cli.main().
- **Playground**: Repo `playground/zush_demo`; run e.g. `uv run zush --mock-path ./playground demo greet` or `zush self map`.
- **Persisted plugin config**: `Plugin.persistedCtx()` now persists data by plugin package name via `cfg-index.json` and stores payload files under `cfgs/{uuid}/`, with support for plain text, JSON, TOML, and YAML. Matching package names intentionally share the same config entry.
- **Temporary storage helper**: `temporary_storage()` yields a tempdir-backed `DirectoryStorage` and cleans it up automatically.
- **Tests**: 38 tests (paths, config, context, cache, plugin_loader, discovery, group including self reserved); pytest; all passing.

## What was just completed

- **Discovery helper extraction**: `run_discovery()` now delegates env list building and live env scanning to `utils/discovery.py`, with added direct tests for those helpers. Full suite now passes with 89 tests.
- **Second-pass utils refactor**: Split mixed utility concerns into focused modules (`utils/cli.py`, `utils/plugin_runtime.py`, `utils/plugin_loader.py`), moved group command merging into `utils/group.py`, and added direct tests for extracted utility helpers. Full suite now passes with 87 tests.
- **Test harness decoupling**: Playground subprocess tests now copy fixture plugins into temp envs and force UTF-8 subprocess I/O; the Applewood test now builds a local fixture package instead of depending on an external checkout.
- **Internal utils delegation**: Added `src/zush/utils/` and moved shared helper implementations there while keeping runtime behavior unchanged. Full suite passes after the refactor.
- **Mountable zush**: ZushStorage protocol + default_storage() + DirectoryStorage; load_config(storage=), read_cache/read_sentry/write_cache/write_sentry(storage=); run_discovery(storage=); create_zush_group(name, config, storage, mock_path) returning Click Group; main() refactored to use factory. Embedding: parent app can add_command(create_zush_group(), "zush").
- **Env resolution flag**: `include_current_env` added to config; `zush.envs.current_site_package_dirs()` added; discovery now optionally scans the current interpreter's site-packages when the flag is true. All 65 tests pass.
- **Persistence layer**: Added cfg index/storage paths, `zush.persistence`, runtime binding of helper plugins, and tests proving persisted state survives across invocations and is shared by matching package names. Full suite now passes with 74 tests.
- **Temporary storage helper**: Added `zush.paths.temporary_storage()` plus tests and README docs for isolated tempdir-backed config/cache/cfg storage.

## What's left (optional)

- More reserved commands under `self` (e.g. config dump, cache clear).
- Plugin author doc (hook attribute names, ZushPlugin contract, persistedCtx usage).
- Full storage provider (read/write interface) for non-file backends.

## Current status

- Implementation complete and tested. CLI works with or without config; --mock-path for testing without editing config; self map for inspecting the command tree.

## Known issues

- Migration guidance needed tightening: real package migrations must keep `__zush__.py` inside the installed package that matches `env_prefix`, unless the task explicitly includes shipping and configuring a separate plugin package.
- `self map` must be validated against real installed-package layouts, not only playground scenarios.

## Recent fixes

- Fixed `self map` root resolution so the printed tree reflects the live root group instead of only the reserved `self` subtree.
- Fixed discovery for unchanged envs so sentry can skip rescanning without dropping cached plugin packages from the live command tree.
- Fixed first-run behavior so a missing `~/.zush/config.toml` no longer leaves zush with no scanned envs by default; zush now writes a bootstrap config with current-env scanning enabled.
- Added `zush self config` so users can open the active config folder directly, honoring custom storage when zush is embedded.

## Evolution of decisions

- Custom Click group (ZushGroup) with custom invoke for hooks and sub_ctx.obj.
- Plugin export via ZushPlugin instance and .commands dict; hooks inferred by instance type (before_cmd, after_cmd, on_error, on_ctx_match).
- beforeCmd/afterCmd regex; onCtxMatch equality; first-wins merge; --mock-path for overload without config; reserved group `self` with `map`.
- Documentation and skill guidance now explicitly require migration work to align installed package name, `env_prefix`, scanned env path, and `__zush__.py` placement before treating discovery as a cache or invalidation problem.
