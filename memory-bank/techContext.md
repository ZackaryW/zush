# Tech Context: zush

## Technologies

- **Language**: Python 3.12+.
- **CLI**: Click, with a **custom group** (ZushGroup) for hooks and custom behavior.
- **Build**: uv (pyproject.toml; `uv_build`).
- **Tests**: pytest (optional dev dep); tests in `tests/`, pythonpath `src`.

## Paths

- **Project layout**: `src` layout; package `zush` under `src/zush/`.
- **Entry point**: `zush = "zush:main"` (console script).
- **User config/cache/sentry**: `~/.zush/` (pathlib for OS-agnostic paths).
- **Playground**: Repo `playground/` holds sample plugins (e.g. `zush_demo`); use with `--mock-path ./playground` or config `playground`.

## Modules (src/zush)

- **configparse/config**: `Config`, `default_config()`, `ensure_config_exists()`, `load_config()`.
- **core/storage**: config/cache/sentry/services/cfg path helpers, `ZushStorage`, `default_storage()`, `DirectoryStorage`.
- **core/envs**: Helpers for resolving environment roots (e.g. `current_site_package_dirs()` for the current interpreter).
- **core/context**: `ZushCtx` (observable dict), `HookRegistry` (before_cmd, after_cmd, on_error).
- **core/cache**: read/write cache and sentry with optional storage; `is_env_stale()`.
- **core/persistence**: read/write `cfg-index.json` and manage persisted plugin payload files under `cfgs/{uuid}/`.
- **pluginloader/loader**: `load_plugin(package_path)` → `(instance, commands_dict)`.
- **pluginloader/plugin**: `Plugin`, `Section`, `PluginCommand`, helper plugin author surface.
- **pluginloader/runtime**: plugin hook registration, runtime binding, provider/global registration.
- **core/discovery**: `run_discovery(config, mock_path=None, no_cache=False, storage=None)`, honoring `include_current_env` when building `envs_to_scan`.
- **core/group**: `merge_commands_into_group()` (first-wins; skip `self`), `ZushGroup`, `add_reserved_self_group()`.
- **mocking/cli**: `parse_mock_path()`.
- **mocking/storage**: `temporary_storage()`.
- **__init__**: re-exports `create_zush_group()` and `main()` from `core.bootstrap`.

## Dependencies

- **click** (runtime).
- **PyYAML** (runtime; YAML persistence support).
- **pytest** (dev optional).

## Core API surface

- **create_zush_group(name, config, storage, mock_path)**: Factory that returns a built ZushGroup for standalone use or embedding. Omitted config/storage use defaults.
- **ZushStorage**: Protocol (config_dir, config_file, cache_file, sentry_file). default_storage(), DirectoryStorage(base_path).
- **ZushCtx**: Dict-like, observable; register_on_ctx_match(key, value, callback).
- **HookRegistry**: register_before_cmd, register_after_cmd, register_on_error; run_* methods used by ZushGroup.
- **Reserved**: `self` group with `map` command (tree of commands).
