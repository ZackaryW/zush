---
name: zush-configure
description: Configure Zush namespaces, read-only remote map.toml aliases and exclusions, local alias overlays, and state paths. Use when an agent needs to enroll or remove a GitHub owner, author or review a .zush repository configuration, bind or unbind an alias, or relocate Zush state.
---

# Configure Zush

## Preserve the configuration boundaries

- Treat the authenticated user's visible GitHub repository named `.zush` as optional and read-only.
- Never create, commit, or push `.zush` on the user's behalf unless separately asked outside a Zush configuration operation.
- Do not load configuration from an enrolled organization's `.zush` repository; only the authenticated user's repository supplies `map.toml`.
- Keep local aliases and tombstones in local Zush state, separate from the remote repository.

## Configure namespaces

Use the public commands:

```console
zush namespace add Pathverse
zush namespace list
zush namespace remove Pathverse
```

`namespace add` must successfully enumerate the GitHub owner before persisting trust. Enrollment covers every visible current or future repository under that owner. Removal blocks new executions but does not delete Saucepan checkouts.

The authenticated owner needs no enrollment and is addressed with `~`.

## Author remote aliases and exclusions

Use this `map.toml` shape:

```toml
[commands.deploy]
target = { owner = "~", repo = "tools", path = "scripts.deploy" }
default_args = ["staging"]
default_map = { retries = 2, dry_run = false }

[namespaces.alice]
exclude = ["archive-*", "private-scripts"]
```

For an alias target, require string fields `owner`, `repo`, and `path`. `owner` is `"~"` or an explicitly enrolled GitHub owner. Preserve TOML types in `default_map`. Exclusions are case-sensitive shell-style repository-name patterns and are applied before acquisition.

Invalid TOML or an invalid record shape prevents affected execution; do not silently drop malformed entries.

## Configure local aliases

```console
zush alias bind ship ~tools:scripts.deploy
zush alias unbind ship
```

A local binding overrides a remote alias of the same name. Unbinding records a local tombstone and can hide a remote-only alias. These commands do not edit remote `map.toml`.

## Configure state paths

Use `ZUSH_HOME` to relocate all local Zush state and `ZUSH_SAUCEPAN` to select a Saucepan executable. Record these in the calling environment or its normal environment-management mechanism; do not embed machine-specific paths in the remote `.zush` repository.
