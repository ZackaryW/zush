# Active Context: zush

## Current focus

Mountable zush is implemented. Next optional work: document embedding in README or plugin guide; more reserved commands; full read/write storage provider for non-file backends.

## Recent changes

- **create_zush_group(name, config, storage, mock_path)**: Factory returns built ZushGroup; main() uses it. Embedding: `app.add_command(create_zush_group(), "zush")`.
- **ZushStorage**: Protocol + default_storage() + DirectoryStorage(base). config/cache/discovery accept optional storage.
- **Reserved group `self`**: Plugin commands under `self` skipped; built-in `self` + **map**.
- **`--mock-path` / `-m`**: Overload env, no cache. **Playground** and **zush_hooks_demo**; ZushGroup init fix (zush_ctx is not None check).

## Active decisions and considerations

- **Mountable**: Zush as a Click group that can be added to another app via `app.add_command(create_zush_group(...), "zush")`. Custom envs = pass Config; custom storage = pass ZushStorage (paths-based first).
- **Storage**: Paths-based abstraction (config_dir + file paths); same file I/O, pluggable base path. Optional later: full read/write provider for non-file backends.
- **Custom Click group**: ZushGroup holds ZushCtx and HookRegistry; first-wins merge; reserved `self` added after plugins.
- **Hooks**: Inferred from plugin instance (before_cmd, after_cmd, on_error, on_ctx_match); never exposed as commands.

## Important patterns and preferences

- TDD: write failing test, then implement; keep all existing tests green.
- Cline reads the Memory Bank at task start; it is the source of truth for project context.
