# Progress: zush

## What works

- **Plugin parent help summaries**: Helper-built plugin commands now show their Click usage pieces in parent help listings, so nested command help includes option and argument signatures alongside the short prose description while still respecting Click's short-help width limit for longer signatures.
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
- **Runtime providers and services**: Plugins can declare static globals with `provide(...)`, lazy providers with `provide_factory(...)`, provider teardown/rebuild rules, detached services, custom service control interfaces, and provider-facing runtime lifecycle calls through `ZushPlugin.runtime`.
- **Playground provider/service demo**: `playground/zush_provider_service_demo` shows one plugin package owning both a provider and a service control interface, with subprocess coverage through `uv run zush --mock-path ...`.
- **Tests**: full pytest suite passes with 105 tests.

## What was just completed

- **Parent help signature fix**: Added regression coverage proving parent help for helper-built commands includes usage pieces like `[OPTIONS] [SOURCE]`, then refined the custom command subclass so longer signatures still honor Click's short-help width limit and truncate cleanly. Full suite now passes with 105 tests.
- **Provider rebuild/teardown and playground demo**: Added service-aware provider invalidation with teardown hooks, so `provide_factory(..., service=..., recreate_on_restart=True, teardown=...)` can rebuild control surfaces after service stop/restart. Added a new playground demo package plus subprocess coverage showing one plugin package owning both a service and a provider.
- **Provider factory and control-interface runtime**: Added `Plugin.provide_factory(...)`, lazy global materialization through `zush.runtime.g`, a bound plugin runtime facade for ensuring owned services are ready before provider creation, and service control-interface support with subprocess fallback. Focused runtime/service tests now cover both custom lifecycle control and provider-triggered service startup.
- **Flask/httpx restart-health coverage**: Expanded `tests/test_services_flask.py` with a second real detached-service integration test that forces an unhealthy Flask healthcheck, verifies `self services ... --status` triggers auto-restart, and confirms the service recovers with clean state. README service docs now describe healthcheck callbacks and auto-restart behavior.
- **Flask/httpx integration test**: Added `tests/test_services_flask.py` plus dev dependencies for Flask and httpx. The test spins up a real detached Flask service through zush, drives transaction-style state changes through plugin commands, and validates restart behavior.
- **Runtime store and service controller**: Added `zush.runtime.g` for process-local shared objects, helper support for `Plugin.provide(...)`, a detached service definition/controller layer with persisted `services.json` state, and built-in `self services` lifecycle commands. Full suite now passes with 95 tests.
- **Discovery helper extraction**: `run_discovery()` now delegates env list building and live env scanning to `utils/discovery.py`, with added direct tests for those helpers. Full suite now passes with 89 tests.
- **Second-pass utils refactor**: Split mixed utility concerns into focused modules (`utils/cli.py`, `utils/plugin_runtime.py`, `utils/plugin_loader.py`), moved group command merging into `utils/group.py`, and added direct tests for extracted utility helpers. Full suite now passes with 87 tests.
- **Test harness decoupling**: Playground subprocess tests now copy fixture plugins into temp envs and force UTF-8 subprocess I/O; the Applewood test now builds a local fixture package instead of depending on an external checkout.
- **Internal utils delegation**: Added `src/zush/utils/` and moved shared helper implementations there while keeping runtime behavior unchanged. Full suite passes after the refactor.
- **Mountable zush**: ZushStorage protocol + default_storage() + DirectoryStorage; load_config(storage=), read_cache/read_sentry/write_cache/write_sentry(storage=); run_discovery(storage=); create_zush_group(name, config, storage, mock_path) returning Click Group; main() refactored to use factory. Embedding: parent app can add_command(create_zush_group(), "zush").
- **Env resolution flag**: `include_current_env` added to config; `zush.envs.current_site_package_dirs()` added; discovery now optionally scans the current interpreter's site-packages when the flag is true. All 65 tests pass.
- **Persistence layer**: Added cfg index/storage paths, `zush.persistence`, runtime binding of helper plugins, and tests proving persisted state survives across invocations and is shared by matching package names. Full suite now passes with 74 tests.
- **Temporary storage helper**: Added `zush.paths.temporary_storage()` plus tests and README docs for isolated tempdir-backed config/cache/cfg storage.
- **Windows `self config` fix**: `zush self config` now opens the config directory with the native Windows opener when available and raises a ClickException on launch failure instead of silently succeeding. Focused group coverage was added and the full suite now passes with 103 tests.

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
