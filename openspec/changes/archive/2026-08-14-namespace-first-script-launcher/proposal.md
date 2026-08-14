## Why

Zush should make every script in a GitHub namespace directly runnable without requiring each repository or file to declare a Zush plugin, command catalog, or argument grammar. The source-management work already delivered by Saucepan can own repository lifecycle while Zush stays focused on namespace resolution, local script dispatch, structured invocation, and personal aliases.

## What Changes

- Preserve `zush` as the package, import namespace, console command, state-directory, and public product identity; `zush-2` is only this repository worktree's name.
- **BREAKING**: Define Zush as a clean-break GitHub-backed script launcher; brands, hooks, services, imported Python callables, repository command manifests, and repository-declared virtual namespaces are not part of this product boundary.
- Make the authenticated GitHub user's owned repositories available through `~`, and allow explicitly trusted organization or user namespaces to be added.
- Address scripts as `~repo:path.to.script` or `owner/repo:path.to.script`, resolving the repository before acquiring it and resolving the script only from the managed local checkout.
- Generate a private local Saucepan central index from GitHub namespace enumeration so manifest-less repositories can be installed without user-authored acquisition metadata.
- Delegate install, path, provenance, update, and uninstall lifecycle to Saucepan; updates remain explicit rather than occurring during execution.
- Execute directly executable files and unambiguous `.py`, `.ps1`, `.sh`, `.cmd`, and `.bat` matches, with raw argv passed after `--`.
- Build optional typed JSON input from alias defaults, `--map`, `--var`, and `--casted`, and expose it to the script through `ZUSH_INPUT_FILE` without consuming stdin.
- Load aliases and exclusions from an optional read-only `.zush` GitHub repository, layer local aliases above it, and provide `zush alias bind` and `zush alias unbind` without committing or pushing.

## Capabilities

### New Capabilities

- `namespace-discovery`: Authenticated-user shorthand, explicit namespace enrollment and trust, GitHub enumeration, and repository exclusion behavior.
- `repository-materialization`: Generated local Saucepan index entries, provenance-based identity lookup, managed checkout lifecycle, and explicit updates.
- `script-execution`: Public address grammar, deterministic local path resolution, runner selection, ambiguity handling, and raw argument execution.
- `structured-input`: Typed invocation values, precedence and coercion rules, temporary JSON transport, and cleanup.
- `command-aliases`: Optional `.zush` repository configuration, local overlay bindings, target expansion, default arguments and maps, and non-mutating remote behavior.

### Modified Capabilities

None. This repository has no canonical product specifications yet.

## Impact

- `src/zush`: Replace the scaffold entry point with namespace, configuration, Saucepan coordination, resolution, execution, and alias modules.
- `features/<capability>/`: Add independently runnable Behave roots using thin bindings and shared lifecycle under `features/support/`.
- `tests/`: Add focused unit matrices for parsing, path resolution, index generation, overlay precedence, coercion, and serialization.
- Runtime integrations: authenticated `gh`, a Zush-managed Saucepan workspace and binary, Git, and available native script interpreters.
- Persistent state: local namespace and alias overlay state, optional read-only `.zush` repository configuration, and a generated disposable local Saucepan index.
