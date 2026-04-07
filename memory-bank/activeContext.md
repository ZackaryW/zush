# Active Context: zush

## Current focus

The source tree has now been structurally reorganized under `src/zush/` into five major folders: `pluginloader`, `configparse`, `core`, `mocking`, and `utils`. The package root remains thin and only exposes the bootstrap surface (`create_zush_group`, `main`), while runtime/storage/discovery concerns now live under `core`, plugin author/loading concerns under `pluginloader`, config loading under `configparse`, and mock-path/temp-storage helpers under `mocking`.

Helper-built plugin commands now expose their option and argument signature in parent help listings. The shared plugin builder uses a custom Click command subclass so group help can show summaries like `[OPTIONS] [SOURCE] ...` instead of prose-only descriptions, while still honoring Click short-help width limits for longer signatures.

Provider-owned service lifecycle is now implemented. Helper plugins can declare a service, bind a lazy provider factory to that service, expose plugin-facing lifecycle commands through `ZushPlugin.runtime`, and opt into provider teardown/rebuild when the service restarts or stops. Config still supports `include_current_env`, persisted plugin config still uses the cfg index + UUID payload directories, and storage still supports `temporary_storage()` for isolated runs.

Recent migration lesson: when moving a real package under zush discovery, `__zush__.py` must live in the installed package directory that matches the active `env_prefix`. Creating a separate sibling plugin package without also changing packaging and config is a predictable real-world failure mode.

Recent discovery lesson: unchanged envs still need to contribute live plugins. Sentry can skip a filesystem rescan, but discovery must reload cached package paths into the live command tree or top-level help can degrade to `self` only even though plugin commands still exist in the scanned env.

Recent bootstrap lesson: when `~/.zush/config.toml` is missing entirely, zush should create a bootstrap config automatically instead of silently running with no scanned envs. The generated config should enable `include_current_env` so installed plugins in the active interpreter are visible on first run.

## Recent changes

- **Five-folder source revamp**: `src/zush/` now centers on `pluginloader/`, `configparse/`, `core/`, `mocking/`, and `utils/`. The previous flat module layout has been retired in favor of domain packages.
- **Thin root bootstrap**: `src/zush/__init__.py` now delegates directly to `core.bootstrap` so the package root stays minimal while the implementation lives under the new structure.
- **Runtime/storage move**: Discovery, group orchestration, context, runtime globals, services, persistence, cache, env helpers, and storage abstractions now live under `src/zush/core/`.
- **Plugin/config move**: Plugin author APIs and plugin loading/runtime binding now live under `src/zush/pluginloader/`, and config parsing/loading now lives under `src/zush/configparse/`.
- **Mocking package**: Mock CLI parsing and disposable temp storage now live under `src/zush/mocking/`, giving mock-path infrastructure a first-class home.
- **Refactor validation via uv**: The reorganized tree passes the full suite with `uv run --extra dev pytest`.
- **Signature-aware parent help summaries**: Helper-built plugin commands now use a custom Click command subclass that prefixes parent help listings with the child command usage pieces, so nested help output includes option and argument specs instead of only the prose help string. Long signatures still respect Click's short-help width limit and truncate cleanly.
- **Provider invalidation and teardown**: Lazy providers can now declare `service=...`, `recreate_on_restart=True`, and `teardown=...`. zush invalidates those providers on service lifecycle changes, runs the teardown hook for the stale instance, and rebuilds the provider lazily on next access.
- **Provider/service playground demo**: Added `playground/zush_provider_service_demo`, a concrete example of one plugin package owning a service control interface and a lazy provider factory with plugin-facing start/stop/restart/status commands.
- **Provider-owned service lifecycle**: Helper plugins can now register lazy provider factories with `Plugin.provide_factory(...)`. Factories are evaluated on first access through `zush.runtime.g`, can receive a bound plugin runtime object, and can call `runtime.ensure_service(...)` to start and wait on services declared by the same plugin.
- **Custom service control interfaces**: `Plugin.service(...)` now accepts a `control` object with lifecycle methods and a `terminate_fallback` flag. zush uses the control interface first for start/stop/restart/status and falls back to OS-level termination only when configured.
- **Healthcheck auto-restart coverage**: Expanded the Flask service integration coverage to include an unhealthy health endpoint. The new test flips the service into a 503 health state, verifies `self services <name> --status` detects the failure, auto-restarts the service, and confirms the Flask app comes back healthy with reset in-memory state.
- **Flask service integration coverage**: Added an end-to-end integration test that creates a temporary Flask-backed service plugin, starts it through `self services`, uses plugin commands plus `httpx` to exercise transactional HTTP behavior, restarts the service, and verifies the state resets as expected.
- **Runtime globals and services**: Added a process-local `zush.runtime.g` global object store, helper-based `Plugin.provide(...)` support, plugin-declared detached services, persisted `services.json` state, and built-in `zush self services <name> --start|--stop|--restart|--status` control with auto-restart support.
- **Discovery orchestration split**: Extracted environment selection and live env scanning helpers into `src/zush/utils/discovery.py`, leaving `run_discovery()` focused on cache/sentry orchestration and stale-env handling.
- **Utils boundary tightened**: Split the earlier catch-all utility module into focused helpers for CLI arg parsing, plugin runtime binding/hook registration, and plugin-instance lookup. Group command merging now also lives in `src/zush/utils/group.py`.
- **Internal utils package**: Added `src/zush/utils/` and delegated helper implementations for discovery, persistence, group tree rendering, env path deduplication, plugin hook/runtime helpers, and plugin-instance lookup into utility modules while preserving existing module behavior.
- **create_zush_group(name, config, storage, mock_path)**: Factory returns built ZushGroup; main() uses it. Embedding: `app.add_command(create_zush_group(), "zush")`.
- **ZushStorage**: Protocol + default_storage() + DirectoryStorage(base). config/cache/discovery accept optional storage.
- **Reserved group `self`**: Plugin commands under `self` skipped; built-in `self` + **map**.
- **Reserved group `self`**: Plugin commands under `self` skipped; built-in `self` now includes **map** and **config**.
- **`self config` launch behavior**: Opening the config directory must not fail silently. On Windows, use the native directory opener; on any platform, nonzero open failures should raise a ClickException.
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
- **Provider/service ownership model**: Keep plugin import side-effect free. Providers may depend on services, but service readiness should be ensured lazily at provider access time through the bound plugin runtime rather than during discovery.
- **Hooks**: Inferred from plugin instance (before_cmd, after_cmd, on_error, on_ctx_match); never exposed as commands.
- **Migration packaging rule**: For real migrations, `__zush__.py` belongs inside the installed package directory that zush will actually scan. Do not split a migrated package into a sibling plugin package unless the task explicitly includes packaging/build changes for that separate package.
- **Cached env behavior**: Sentry is only an optimization for rescanning. It must not suppress live plugin registration for unchanged envs.

## Important patterns and preferences

- TDD: write failing test, then implement; keep all existing tests green.
- Cline reads the Memory Bank at task start; it is the source of truth for project context.
