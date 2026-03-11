# Active Context: zush

## Current focus

Core implementation is complete and tested. Current state: config load, env discovery (with optional playground and --mock-path), plugin load, custom Click group with hooks, cache/sentry, ZushCtx, reserved **self** group with **self map** (command tree). Focus can shift to additional reserved commands, more hook conveniences, or documentation.

## Recent changes

- **Reserved group `self`**: Plugin commands under `self` are skipped in merge; built-in group `self` added after merge with command **`map`** (tree-style command map).
- **`--mock-path` / `-m`**: CLI flag to use a single path as overload env and disable caching (no config edit).
- **Playground**: Optional `playground` in config; repo has `playground/` with `zush_demo`; first-wins merge so playground takes precedence.
- Full implementation of paths, config, context (ZushCtx + HookRegistry), cache, plugin_loader, discovery, group (ZushGroup, merge, first-wins, invoke with hooks), main() with argv parsing for --mock-path.

## Next steps

- Optional: more reserved commands under `self` (e.g. config dump, cache clear).
- Optional: document plugin hook attribute names (before_cmd, after_cmd, on_error, on_ctx_match) in a plugin author guide.
- Optional: tests for `zush self map` output.

## Active decisions and considerations

- **Custom Click group**: ZushGroup holds ZushCtx and HookRegistry; runs beforeCmd/afterCmd/onError; sets sub_ctx.obj = zush_ctx; first-wins merge; reserved `self` added after plugins.
- **Plugin export**: ZushPlugin dict; plugin instance in `__zush__.py`; hooks inferred by instance type (before_cmd, after_cmd, on_error, on_ctx_match).
- **Cache/sentry**: Used unless `--mock-path` (no_cache); sentry staleness by mtime.
- **Reserved name**: `self` is reserved; merge skips any plugin key whose first segment is `self`.

## Important patterns and preferences

- Prefer resolving plugins from envs (or mock_path) + env_prefix; use sentry to avoid re-parsing when not using --mock-path.
- Cline reads the Memory Bank at task start; it is the source of truth for project context.
