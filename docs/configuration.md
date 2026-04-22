# Configuration

zush reads configuration from ~/.zush/config.toml.

If the file does not exist yet, zush creates a bootstrap config on first run.

## Supported Keys

| Key | Meaning |
|---|---|
| envs | Directories to scan for plugin packages. |
| env_prefix | Allowed package name prefixes. Default: ["zush_"]. |
| playground | Optional directory scanned first for local development overrides. |
| include_current_env | When true, also scan the current Python environment site-packages. |
| disabled_extensions | Optional list of extension keys to skip during discovery. |

Example:

```toml
envs = ["/path/to/plugins", "/another/path"]
env_prefix = ["zush_", "my_"]
playground = "/path/to/zush/playground"
include_current_env = true
disabled_extensions = ["zush_demo"]
```

zush stores config, cache, and runtime files under ~/.zush/ by default.

On Windows, self config uses the native directory opener and surfaces a CLI error if the folder cannot be opened.

## Discovery Notes

- zush discovers directories whose names match one of env_prefix.
- A discovered plugin package must contain __zush__.py at package root.
- --mock-path (or -m) scans only the given directory and disables cache for that run.

Example:

```bash
uv run zush --mock-path ./playground self map
uv run zush --mock-path ./playground demo greet
```
