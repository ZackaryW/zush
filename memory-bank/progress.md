# Progress: zush

## What works

- **Config**: load_config() from ~/.zush/config.toml (envs, env_prefix, optional playground).
- **CLI overload**: `--mock-path` / `-m` parsed in main(); single env, no cache.
- **Discovery**: run_discovery() scans envs (or mock_path), loads plugins, merges tree, updates cache/sentry unless no_cache; playground in config scanned first.
- **Plugin loader**: load_plugin() from __zush__.py; instance with .commands; prefer ZushPlugin.
- **Context**: ZushCtx (observable dict, onCtxMatch on set), HookRegistry (before/after/onError with regex/type).
- **Group**: ZushGroup with hooks, sub_ctx.obj = zush_ctx; merge_commands_into_group (first-wins; skip reserved `self`); add_reserved_self_group (self + map).
- **Reserved self**: Group `self` with command `map` (tree-style command map); plugins cannot register under `self`.
- **main()**: argv parse → config → discovery → hooks → build CLI → add self → cli.main().
- **Playground**: Repo `playground/zush_demo`; run e.g. `uv run zush --mock-path ./playground demo greet` or `zush self map`.
- **Tests**: 38 tests (paths, config, context, cache, plugin_loader, discovery, group including self reserved); pytest; all passing.

## What was just completed

- **Mountable zush**: ZushStorage protocol + default_storage() + DirectoryStorage; load_config(storage=), read_cache/read_sentry/write_cache/write_sentry(storage=); run_discovery(storage=); create_zush_group(name, config, storage, mock_path) returning Click Group; main() refactored to use factory. Embedding: parent app can add_command(create_zush_group(), "zush"). All 52 tests pass.

## What's left (optional)

- More reserved commands under `self` (e.g. config dump, cache clear).
- Plugin author doc (hook attribute names, ZushPlugin contract).
- Full storage provider (read/write interface) for non-file backends.

## Current status

- Implementation complete and tested. CLI works with or without config; --mock-path for testing without editing config; self map for inspecting the command tree.

## Known issues

- None. Cache/sentry and discovery behave as designed; reserved self is enforced.

## Evolution of decisions

- Custom Click group (ZushGroup) with custom invoke for hooks and sub_ctx.obj.
- Plugin export via ZushPlugin instance and .commands dict; hooks inferred by instance type (before_cmd, after_cmd, on_error, on_ctx_match).
- beforeCmd/afterCmd regex; onCtxMatch equality; first-wins merge; --mock-path for overload without config; reserved group `self` with `map`.
