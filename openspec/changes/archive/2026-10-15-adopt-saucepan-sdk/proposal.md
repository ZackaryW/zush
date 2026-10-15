# Proposal

## Why

Zush-2 already provides the desired small GitHub CLI launcher, but its Saucepan 0.3 command adapter and vendored installer cannot use the current SDK. Adapting that foundation preserves working command behavior while adding discovery of `.zush` content in installed repositories.

## What Changes

- Replace legacy bucket/index/install/path commands with the public Python SDK, exact Git provenance, persistent groups, and retained output generations.
- Preserve GitHub CLI namespace discovery, explicit enrollment, exclusions, direct addresses, structured inputs, and local alias overlays.
- Discover repository-local `.zush/map.toml` commands from installed outputs alongside the authenticated owner's central `.zush` repository.
- Keep ordinary execution on the installed revision; make updates explicit and retain outputs through execution and configuration reads.
- **BREAKING** Remove the vendor folder, private binary downloader, old Saucepan workspace configuration, and legacy metadata support. Use an externally installed Saucepan 0.10-compatible executable and standard root resolution with explicit overrides.
- **BREAKING** Raise the Python minimum to 3.12 for the SDK and use a reproducible external dependency.

## Capabilities

### New Capabilities

- `repository-command-discovery`: Discover repository-local `.zush` commands without downloading every visible repository or creating ambiguous global aliases.

### Modified Capabilities

- `repository-materialization`: Replace generated legacy indexes with SDK source identity, retained output generations, and failure-safe publication.
- `runtime-compatibility`: Require Python 3.12 and an external current Saucepan SDK/runtime instead of vendored bootstrap code.

## Impact

Targets this `zush-2` working tree, not the separate `zush` repository. Changes affect `src/zush/saucepan.py`, application orchestration, configuration/discovery helpers, paths/state, packaging, tests, behavior features, and README usage instructions. Saucepan SDK implementation and the richer old Zush services/hooks are outside scope. Active OpenSpec files remain outside implementation commits; no pushes are authorized.

The current adaptation also adopts the manager-owned `explicit-update` profile through Python SDK 0.2.0, with expanded immutable inputs persisted for retry.
