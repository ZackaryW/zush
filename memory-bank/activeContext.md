# Active Context: zush

## Current focus

Mountable zush is implemented. Config now has an `include_current_env` flag and discovery can optionally scan the current interpreter's site-packages via `zush.envs.current_site_package_dirs()`. Persisted plugin config is now supported through a dedicated cfg index file and UUID-backed payload directories. Same package names intentionally share the same persisted config entry. Storage also provides a `temporary_storage()` helper for isolated tempdir-backed runs. Next optional work: expand persistence tests for malformed files and nested TOML structures.

Recent migration lesson: when moving a real package under zush discovery, `__zush__.py` must live in the installed package directory that matches the active `env_prefix`. Creating a separate sibling plugin package without also changing packaging and config is a predictable real-world failure mode.

Recent discovery lesson: unchanged envs still need to contribute live plugins. Sentry can skip a filesystem rescan, but discovery must reload cached package paths into the live command tree or top-level help can degrade to `self` only even though plugin commands still exist in the scanned env.

Recent bootstrap lesson: when `~/.zush/config.toml` is missing entirely, zush should create a bootstrap config automatically instead of silently running with no scanned envs. The generated config should enable `include_current_env` so installed plugins in the active interpreter are visible on first run.

## Recent changes

- **Discovery orchestration split**: Extracted environment selection and live env scanning helpers into `src/zush/utils/discovery.py`, leaving `run_discovery()` focused on cache/sentry orchestration and stale-env handling.
- **Utils boundary tightened**: Split the earlier catch-all utility module into focused helpers for CLI arg parsing, plugin runtime binding/hook registration, and plugin-instance lookup. Group command merging now also lives in `src/zush/utils/group.py`.
- **Internal utils package**: Added `src/zush/utils/` and delegated helper implementations for discovery, persistence, group tree rendering, env path deduplication, plugin hook/runtime helpers, and plugin-instance lookup into utility modules while preserving existing module behavior.
- **create_zush_group(name, config, storage, mock_path)**: Factory returns built ZushGroup; main() uses it. Embedding: `app.add_command(create_zush_group(), "zush")`.
- **ZushStorage**: Protocol + default_storage() + DirectoryStorage(base). config/cache/discovery accept optional storage.
- **Reserved group `self`**: Plugin commands under `self` skipped; built-in `self` + **map**.
- **Reserved group `self`**: Plugin commands under `self` skipped; built-in `self` now includes **map** and **config**.
- **`--mock-path` / `-m`**: Overload env, no cache. **Playground** and **zush_hooks_demo**; ZushGroup init fix (zush_ctx is not None check).
- **Persisted plugin config**: Added `cfg-index.json` and `cfgs/` storage paths, a new `zush.persistence` module, and runtime binding for `zush.plugin.Plugin.persistedCtx(...)` supporting plain text, JSON, TOML, and YAML payloads keyed by plugin package name. Matching package names intentionally reuse the same cfg UUID.
- **Temporary storage helper**: Added `zush.paths.temporary_storage()` to create an isolated tempdir-backed `DirectoryStorage` for tests, demos, and disposable sessions.
- **Cached discovery rehydration**: When an env is unchanged according to sentry, discovery now reloads plugin packages from cached package paths instead of dropping that env from the live command tree.
- **Default config bootstrap**: Missing `config.toml` is now created automatically on first run with `env_prefix = ["zush_"]` and `include_current_env = true`.

## Active decisions and considerations

- **Mountable**: Zush as a Click group that can be added to another app via `app.add_command(create_zush_group(...), "zush")`. Custom envs = pass Config; custom storage = pass ZushStorage (paths-based first).
- **Storage**: Paths-based abstraction (config_dir + file paths); same file I/O, pluggable base path. Optional later: full read/write provider for non-file backends.
- **Persistence model**: Keep `cache.json` focused on discovery. Persisted plugin config linkage lives in `cfg-index.json`, while payload files live under `cfgs/{uuid}/...`. Package name is the persistence identity, so matching names share config.
- **Custom Click group**: ZushGroup holds ZushCtx and HookRegistry; first-wins merge; reserved `self` added after plugins.
- **Hooks**: Inferred from plugin instance (before_cmd, after_cmd, on_error, on_ctx_match); never exposed as commands.
- **Migration packaging rule**: For real migrations, `__zush__.py` belongs inside the installed package directory that zush will actually scan. Do not split a migrated package into a sibling plugin package unless the task explicitly includes packaging/build changes for that separate package.
- **Cached env behavior**: Sentry is only an optimization for rescanning. It must not suppress live plugin registration for unchanged envs.

## Important patterns and preferences

- TDD: write failing test, then implement; keep all existing tests green.
- Cline reads the Memory Bank at task start; it is the source of truth for project context.
