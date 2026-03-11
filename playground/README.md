# Zush playground

Packages here simulate zush plugins for testing behavior.

## Run without editing config: `--mock-path`

Use the overload env and disable caching without touching `config.toml`:

```bash
uv run zush --mock-path ./playground demo greet
# or:  uv run zush -m ./playground demo greet
```

- **`--mock-path` / `-m`** — Path to a directory of plugins; only this path is scanned (overload).
- **Caching is disabled** when `--mock-path` is used (no cache/sentry read or write).

## Optional: config.toml

To use the playground without the flag, set `playground` in `~/.zush/config.toml` so it is scanned first (overloaded index env):

```toml
playground = "C:/path/to/zush/playground"
envs = []
env_prefix = ["zush_"]
```

## Packages

- **zush_demo** — Minimal plugin with `zush demo greet` that prints a message. Use it to verify discovery and CLI behavior.
- **zush_hooks_demo** — Demonstrates hook behavior: `hooks run` (before/after), `hooks raise` (on_error), `hooks setctx` (on_ctx_match). Tests in `tests/test_playground_hooks.py` run the CLI to verify.
