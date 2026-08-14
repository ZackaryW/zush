---
name: zush-use
description: Run repository scripts and aliases with Zush, including raw arguments, typed structured input, deterministic script selection, and explicit updates. Use when an agent needs to construct or troubleshoot a zush invocation or explain how a child script receives arguments and ZUSH_INPUT_FILE.
---

# Use Zush

## Select a target

Use `~repo:path.to.script` for the authenticated GitHub owner or `owner/repo:path.to.script` for an enrolled owner:

```console
zush ~tools:scripts.release
zush Pathverse/automation:jobs.cleanup
```

The colon separates the repository from the dot path, so repository names may contain dots. Do not replace the colon with a dot.

Zush resolves exactly one exact executable or suffixed file among `.py`, `.ps1`, `.sh`, `.cmd`, and `.bat`. Missing or multiple candidates are errors. Python uses the active interpreter; other file types require their native runner.

## Pass arguments

Repeat `--arg` for parsed arguments and use `--` before literal remaining tokens:

```console
zush ~tools:deploy --arg staging -- --force --var not-parsed
```

The child receives repeated `--arg` values first and raw tokens second. Zush inherits stdin, stdout, and stderr and returns the child's exit status.

## Pass structured input

```console
zush ~tools:deploy --map '{"retries":2}' --var region=west --casted bool+dry_run=false
```

Build one shallow JSON object in this precedence order:

1. Alias `default_map`
2. Each `--map` JSON object
3. Each `--var key=value` string
4. Each `--casted type+key=value`

Supported cast types are `str`, `int`, `float`, `bool`, and `json`; booleans accept lowercase `true` or `false`. Later values replace the same top-level key without recursively merging objects.

For a nonempty object, the child reads UTF-8 JSON from the path in `ZUSH_INPUT_FILE`. Zush removes that temporary file after the child exits. An empty object does not set the variable.

## Run aliases and updates

Run a configured alias with the same invocation options:

```console
zush run ship --arg production
```

Alias default arguments precede explicit arguments. Alias execution uses the same namespace, Saucepan, script-resolution, input, and process pipeline as a direct address.

Normal execution reuses the current managed checkout and never updates it. Update visible installed repositories only through:

```console
zush update
```

## Apply execution safety

Namespace enrollment grants repository trust; it does not audit script contents. Before an agent executes an unfamiliar repository script, inspect the resolved repository and command intent or obtain the user's explicit approval. Preserve raw arguments exactly and never reinterpret tokens following `--`.
