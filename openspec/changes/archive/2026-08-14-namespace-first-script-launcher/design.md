## Context

The repository is a minimal Python package with no established runtime beyond its console entry point. Saucepan v0.3 already implements authenticated GitHub checkout lifecycle, local and repository-backed central indexes, ref-pinned index manifests, provenance, updates, safe uninstall, and machine-readable state. Its current manifest-resolution chain checks a repository first and registered indexes second, which lets Zush supply acquisition metadata externally without writing into third-party repositories.

The separate `zush` worktree contains a broader plugin-platform migration and remains untouched reference evidence. This repository worktree is named `zush-2`, but it implements and distributes the owner-confirmed clean-break launcher as package, import namespace, console command, state directory, and public product `zush`.

## Goals / Non-Goals

**Goals:**

- Keep repository lifecycle behind one Saucepan subprocess seam.
- Make user configuration optional and make generated acquisition state disposable.
- Keep address, overlay, coercion, and path-selection rules pure and independently testable.
- Exercise public behavior through the installed `zush` command with capability-owned Behave roots.
- Remain Python-standard-library-only at runtime apart from the `gh`, Saucepan, Git, and native runner executables.

**Non-Goals:**

- Pre-clone command discovery, exhaustive remote command help, or typo avoidance before the first checkout.
- Automatic commits or pushes to `.zush`.
- Hooks, services, brands, imported callables, command manifests, front matter, sidecars, or virtual namespace merging.
- Automatic repository refresh during script execution.

## Decisions

### Use argparse and standard-library models

The CLI uses `argparse`, `dataclasses`, `pathlib`, `json`, `tomllib`, `subprocess`, and `tempfile`. This satisfies the Ponytail ladder before adding a general CLI framework. Behave and lint/build tools remain development-only.

### Separate public coordination from pure policy

The public application composes narrow modules for addresses, namespace state, configuration overlays, generated index records, Saucepan subprocess calls, structured input, script resolution, and process execution. Parsing, merging, coercion, and candidate selection receive explicit values and have no network or filesystem side effects where practical.

### Resolve a repository before resolving a script

An address has a colon boundary and therefore identifies `owner/repo` without a remote command tree. Zush validates namespace membership and repository visibility, asks Saucepan for the managed path, and only then maps the dot path locally. A mistyped script may cause a first checkout; that accepted trade-off removes central command catalogs and declaration machinery.

### Generate one local central index from GitHub inventory

Zush writes a deterministic `bucket.json` beneath its local state. Each repository entry uses a stable owner-and-repository manifest identity and the enumerated default-branch commit for both version provenance and the required index ref. It contains no Zush command metadata. The local index is registered once in the private Saucepan workspace and regenerated on namespace refresh.

Repositories with their own Saucepan manifest retain upstream precedence. Zush finds installed state by the `repo` provenance field in `cat index`, so a repository-selected manifest name does not break later path lookup or update.

*Alternatives considered.* A new unmanaged Saucepan mode duplicates capability already expressible through the index chain. Generating a manifest inside the checkout dirties third-party trees and breaks provenance. Maintaining command trees in the index recreates the rejected declaration burden.

### Keep remote configuration and local mutation distinct

The optional authenticated-user `.zush` repository is acquired through the same managed source boundary and read as configuration. Its `map.toml` is never modified by Zush. Local state contains namespace enrollment plus an alias overlay and tombstones; local aliases win. This permits bind/unbind without hidden Git mutations.

### Treat structured input as an optional process protocol

Raw argv is always available. Structured flags create a JSON-compatible object whose temporary file is named only in the child environment. A file avoids environment-size limits and does not consume stdin. Temporary creation and cleanup surround the process invocation even on nonzero exit.

### Use explicit runner adapters

Candidate selection is deterministic and separate from launching. Python uses `sys.executable`; PowerShell, POSIX shell, and Windows command scripts use available native executables; exact executable files run directly. Runner absence and ambiguous suffixes fail before execution.

## Risks / Trade-offs

- **A typo can materialize a repository before local path failure.** → Report the checkout separately and keep subsequent attempts local.
- **Namespace enrollment authorizes future repositories broadly.** → Make the authorization explicit in `namespace add`, listable, removable, and constrained by exclusions.
- **A generated index can become stale.** → Pin every record to an observed commit and refresh only through explicit inventory/update operations.
- **Repository-owned Saucepan identity can differ from generated identity.** → Resolve installed entries by repository provenance.
- **Interpreter availability varies by host.** → Detect the required runner and return a specific error without fallback execution.
- **Remote and local aliases can diverge.** → Expose their origin and use deterministic local precedence plus tombstones.

## Migration Plan

1. Establish the Python CLI and isolated local-state overrides without reading legacy Zush state.
2. Mature pure parsing, inventory conversion, configuration, structured-input, and resolution utilities fail-first.
3. Wire GitHub and Saucepan through injectable subprocess boundaries, then exercise installed-CLI scenarios with isolated fakes.
4. Verify a clean built wheel, supported Python, formatting, lint, unit tests, each capability BDD root, and complete BDD.

There is no automatic migration from the broader plugin implementation. Rollback is removal of this new package and its isolated local workspace; remote repositories are never mutated.
