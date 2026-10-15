# Tasks

Checkpoint coherent, verified slices using zmem-author-commits. Exclude active OpenSpec changes from implementation commits. No pushes or edits to the separate `zush` working tree. If dependency replacement breaks the old adapter, finish the dependent conversion before the first checkpoint rather than preserving legacy shims.

## 1. Current SDK and retained materialization

- [x] 1.1 Replace the vendored resolver and legacy inventory/protocol with the external pinned Python SDK, Python 3.12 packaging, and external manager/root resolution; verify lock reproducibility, import/help/version without I/O, missing-manager diagnostics, and absence of packaged vendor code.
- [x] 1.2 Implement repository provenance, exact commit source selection, immutable flat policies, default unbound groups/pins, and atomic binding records using the existing module boundaries; verify fake-SDK contracts and isolated real-manager first materialization without app/keyring requirements.
- [x] 1.3 Serialize state mutations with bounded file locks and reconcile uncertain preparation receipts using original operation identities; verify concurrent callers, lost receipts, invalid output responses, and non-destructive failure behavior.
- [x] 1.4 Wire execution/configuration reads and explicit updates to retained selections, conserving previous pins; verify ordinary execution does not refresh, update selects a new commit, old readers retain their paths, and failed update preserves the prior binding.
- [x] 1.5 Replace obsolete adapter/bucket tests and behavior fixtures, and document external setup, Python minimum, root overrides, old-state reset, optional protection, and conservative retention; verify materialization tests and the documented setup against an isolated manager.

## 2. Repository-local command discovery

- [x] 2.1 Add strict repository-local `.zush/map.toml` parsing with relative dot paths, typed defaults, and output/.zush containment; verify missing/malformed maps, forbidden cross-repository targets, traversal, symlink escapes, and ambiguous script candidates.
- [x] 2.2 Add installed-only discovery and `zush commands` provenance listing using current visibility/enrollment/exclusions; verify listings do not fetch every repository and excluded or removed namespaces do not contribute commands.
- [x] 2.3 Add qualified `zush run owner/repo:command` and `~repo:command`, plus default deterministic first match and `--no-first`; verify canonical ordering, global alias priority, tombstones, collision diagnostics, and qualified selection independent of ambiguity.
- [x] 2.4 Route selected local commands through existing structured-input/native-runner execution and document central/local map examples and precedence; verify argument/default precedence, inherited streams, exit status, and direct-address regression tests.

## 3. Integration and packaging

- [x] 3.1 Exercise the complete flow with local Git fixtures and the real current SDK/manager: central config, repository map, first acquire, repeated execution, commit update, failed update, and retained previous output; record reproducible commands/results without changing the user's real Saucepan store.
- [x] 3.2 Run the full unit and behavior suites, lint, build, and fresh Python 3.12 wheel installation; verify help/version, installed dependency provenance, no vendor/old protocol traces in live code/docs, and strict OpenSpec validation. Report unavailable platform checks honestly.




## 4. Saucepan 0.10 profile contracts

- [x] 4.1 Pin SDK 0.2.0, require manager 0.10.x, adopt manager-owned explicit-update expansion with immutable saved retry inputs, and verify unchanged retained execution and independent pins.
- [x] 4.2 Verify against the published v0.10.0 Windows manager and SDK wheel with manifest, commit and hash evidence; update user instructions and report platform limits.
