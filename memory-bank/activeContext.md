# Active Context: zush

## Current focus

Mountable zush is implemented. Config now has an `include_current_env` flag and discovery can optionally scan the current interpreter's site-packages via `zush.envs.current_site_package_dirs()`. Persisted plugin config is now supported through a dedicated cfg index file and UUID-backed payload directories. Same package names intentionally share the same persisted config entry. Storage also provides a `temporary_storage()` helper for isolated tempdir-backed runs. Next optional work: expand persistence tests for malformed files and nested TOML structures.

## Recent changes

- **create_zush_group(name, config, storage, mock_path)**: Factory returns built ZushGroup; main() uses it. Embedding: `app.add_command(create_zush_group(), "zush")`.
- **ZushStorage**: Protocol + default_storage() + DirectoryStorage(base). config/cache/discovery accept optional storage.
- **Reserved group `self`**: Plugin commands under `self` skipped; built-in `self` + **map**.
- **`--mock-path` / `-m`**: Overload env, no cache. **Playground** and **zush_hooks_demo**; ZushGroup init fix (zush_ctx is not None check).
- **Persisted plugin config**: Added `cfg-index.json` and `cfgs/` storage paths, a new `zush.persistence` module, and runtime binding for `zush.plugin.Plugin.persistedCtx(...)` supporting plain text, JSON, TOML, and YAML payloads keyed by plugin package name. Matching package names intentionally reuse the same cfg UUID.
- **Temporary storage helper**: Added `zush.paths.temporary_storage()` to create an isolated tempdir-backed `DirectoryStorage` for tests, demos, and disposable sessions.

## Active decisions and considerations

- **Mountable**: Zush as a Click group that can be added to another app via `app.add_command(create_zush_group(...), "zush")`. Custom envs = pass Config; custom storage = pass ZushStorage (paths-based first).
- **Storage**: Paths-based abstraction (config_dir + file paths); same file I/O, pluggable base path. Optional later: full read/write provider for non-file backends.
- **Persistence model**: Keep `cache.json` focused on discovery. Persisted plugin config linkage lives in `cfg-index.json`, while payload files live under `cfgs/{uuid}/...`. Package name is the persistence identity, so matching names share config.
- **Custom Click group**: ZushGroup holds ZushCtx and HookRegistry; first-wins merge; reserved `self` added after plugins.
- **Hooks**: Inferred from plugin instance (before_cmd, after_cmd, on_error, on_ctx_match); never exposed as commands.

## Important patterns and preferences

- TDD: write failing test, then implement; keep all existing tests green.
- Cline reads the Memory Bank at task start; it is the source of truth for project context.
