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

- **paths**: config_dir, config_file, cache_file, sentry_file.
- **config**: Config(envs, env_prefix, playground), load_config().
- **context**: ZushCtx (observable dict), HookRegistry (before_cmd, after_cmd, on_error).
- **cache**: read/write cache and sentry; is_env_stale().
- **plugin_loader**: load_plugin(package_path) → (instance, commands_dict).
- **discovery**: run_discovery(config, mock_path=None, no_cache=False).
- **group**: merge_commands_into_group (first-wins; skip `self`), ZushGroup, add_reserved_self_group (self + map).
- **__init__**: main() (parse --mock-path, load config, discovery, register hooks, build CLI, add self, main()).

## Dependencies

- **click** (runtime).
- **pytest** (dev optional).

## Core API surface

- **ZushCtx**: Dict-like, observable; register_on_ctx_match(key, value, callback).
- **HookRegistry**: register_before_cmd, register_after_cmd, register_on_error; run_* methods used by ZushGroup.
- **Reserved**: `self` group with `map` command (tree of commands).
