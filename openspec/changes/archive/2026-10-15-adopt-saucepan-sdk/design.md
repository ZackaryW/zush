# Design

## Context

See proposal.md for motivation. This working tree has a small argparse application, GitHub CLI enumeration, direct script selection, typed structured inputs, and central/local aliases. `saucepan.py` currently speaks the removed 0.3 bucket/install/path protocol and downloads a private binary using `vendor/saucepan_resolver.py`. `utils/inventory.py` exists only to generate that legacy bucket. The current Python SDK requires Python 3.12 and provides group preparation, exact output receipts, and durable pins. A returned path alone is not retained after a CLI process exits.

## Goals / Non-Goals

Goals: preserve the small launcher, separate GitHub discovery from materialization, make installed paths safe across processes, and discover `.zush` commands predictably.

Non-goals: port old Zush services/hooks/brands, preserve Saucepan 0.3 data, change Saucepan itself, clone every visible repository, edit remote configuration, or publish releases. This replaces the earlier plan in the separate `zush` working tree as the implementation target; that tree remains untouched.

## Decisions

### External SDK and executable

Depend on `saucepan-sdk` from the Saucepan repository Python subdirectory pinned to reviewed release commit `8a2d04e7d2e393c035715520254bdd5955651873`, with a reproducible lock. Raise packaging, lint, and CI Python floors to 3.12. The SDK owns subprocess protocol and structured errors. Resolve the executable from `ZUSH_SAUCEPAN` or PATH, and let Saucepan choose its standard root unless `ZUSH_SAUCEPAN_ROOT` is explicitly set. Use an already initialized manager; report missing runtime/root with actionable instructions. Do not silently download or initialize it. This avoids vendored maintenance and independent binary lifecycle. No marker, legacy protocol, private clone, or compatibility fallback remains.

### Inventory and installed generations

Pass GitHub Repository records directly to the adapter. Register Git sources with GitHub origin and exact commit selectors; keep consumer provenance keyed by canonical `owner/repo`. GitHub CLI remains responsible for enumeration and authentication discovery; private Git access still requires working Git credentials, and failures must explain that distinction without copying tokens into metadata.

Use unbound local groups and pins by default: app registration, scopes, credentials, and keyring are not required. A stable per-ZUSH_HOME consumer identity plus repository identity prevents collisions with other Zush homes in a shared manager. Persist a small binding record containing group UUID/revision, selected output UUID, immutable commit, pin receipt, and origin. Ordinary execution reopens that selected output without refresh. Only first use and explicit update prepare new outputs. Validate the receipt and directory before atomically publishing the selected binding. Register immutable flat policies once and attach UUID references; no nested legacy policy shapes.

Serialize mutations of the same Zush state using the mature `filelock` package with a bounded wait; keep GitHub/network and SDK errors bounded and visible. Use existing atomic state-writing helpers. This is preferable to custom cross-platform locking code. Group revision checks remain authoritative for manager changes. Retain previous generation pins conservatively so another process reading the old binding stays safe. Do not release old pins automatically in this change; document storage trade-off. A process exit is not a native lease, so a bare SDK acquisition path is insufficient.

Persist an operation key and expected group revision before mutation. If transport fails after mutation may have committed, reconcile using the original key/revision; never blindly repeat with a fresh key or execute an unvalidated path. Failed updates retain the previous binding; the update command reports failure. Atomicity is per repository, not a claim that all repositories update transactionally.

### Repository-local command discovery

The authenticated owner's central `.zush/map.toml` keeps its existing schema and local overlay semantics. Installed repositories may additionally provide `.zush/map.toml`. In a repository-local map, `[commands.deploy]` uses `path = "scripts.deploy"` relative to that repository's `.zush` folder, plus optional `default_args` and `default_map`. Cross-repository `target` records are rejected there; central maps remain the place for cross-repository aliases. Reuse existing typed input validation and script candidate rules, not a second execution engine.

`zush commands` lists available commands with provenance and qualified names. `zush run owner/repo:deploy` (and `~repo:deploy`) selects a repository-local command. It may materialize that one explicitly requested visible, enrolled, non-excluded repository, then read its `.zush/map.toml`. Unqualified discovery only inspects already installed, currently eligible repositories, never materializes every visible repository. Missing `.zush` folders/maps are normal. Malformed maps fail with the offending repository/path; paths and symlinks cannot escape the retained output or the repository-local `.zush` boundary.

Per the user's explicit selection, unqualified execution uses **first match by default**: local bindings, then central `.zush` aliases, then repository-local commands ordered by canonical owner/repository. Existing local tombstones hide an unqualified name across discovery layers, while qualified repository invocation remains explicit. `--no-first` fails if multiple visible candidates exist, naming their provenance; it does not silently choose by filesystem/enumeration order. A local override and its overridden central alias remain one effective global candidate, preserving the existing overlay contract. Qualified names remain deterministic regardless of other repositories. Direct `zush ADDRESS` behavior stays repository-relative and separate from `zush run` command-name resolution.

### Maintainable boundaries

Keep `application.py` orchestration, `github.py` discovery, and `saucepan.py` as the application SDK adapter. Place reusable parsing/discovery logic in a focused utility module alongside existing config/addressing/scripts helpers. Keep SDK transport, retention, and source mechanics out of command parsing. Use injected SDK/workspace/process seams in tests. Delete obsolete inventory generation and vendor code rather than retaining adapters for old tests.

## Risks / Trade-offs

- Old state is unsupported: explain reset/re-acquisition; do not delete user state automatically.
- Python 3.11 users must upgrade: verify wheel metadata and fresh Python 3.12 installation.
- Retained old pins consume storage: keep this explicit until safe cleanup is designed; do not risk readers to reclaim space.
- First-match can hide same-named commands: list provenance and provide qualified execution and `--no-first`.
- GitHub access does not guarantee Git transport access: test/report acquisition errors without credential leakage.
- Release downloads may be unavailable: verify with the local current manager and isolated roots; do not declare live GitHub publication verified.

## Migration Plan

Build coherent SDK/materialization, discovery, and integration checkpoints, each with relevant tests and README instructions. Remove vendor and old bucket configuration references from the application, package, tests, and user docs. Preserve historic OpenSpec archives. Exercise a local Git repository through the real SDK/manager in an isolated root, including update failure, retained old output, and script execution. Active change artifacts stay uncommitted until separately archived; all commits are local only.

### Release 0.10 profile adoption

Use SDK 0.2.0 with Saucepan 0.10.x. The manager expands `explicit-update` on first acquisition or an explicit update to a new commit. Persist its catalog and combined UUID references before preparing the group, register those policies explicitly, and reuse precisely those saved inputs on recovery. Existing selections never expand a profile during ordinary execution. Do not reproduce profile defaults in Python. Pins remain an independent until-released policy; profile revision defaults do not release retained generations. No application lifecycle setup is needed. Verify the published manager and wheel against release hashes and manifest before claiming release acceptance.
