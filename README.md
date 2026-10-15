# zush

Zush is a GitHub-backed script launcher. It lets you invoke a script by repository and dot path without requiring
every repository to declare a command catalog.

```console
zush ~tools:scripts.release --arg staging -- --force
zush Pathverse/automation:jobs.cleanup --var region=west
```

`~repo:path.to.script` selects a repository owned by the authenticated GitHub user. An explicit
`owner/repo:path.to.script` is accepted after that owner has been enrolled with `zush namespace add owner`.

## Requirements and installation

Zush requires Python 3.12 or newer, [GitHub CLI](https://cli.github.com/) (`gh`), and a working `gh auth login`.
Script execution additionally requires the native runner for the selected file type.

```console
uv tool install .
zush --version
```

Install Saucepan 0.9.x separately and run `saucepan init` before the first repository operation. Zush uses the external Python SDK pinned to the reviewed release source; it never downloads a private manager or initializes your store automatically. GitHub CLI supplies exact commit metadata, while Saucepan owns retrieval and retained immutable outputs. Private Git repositories additionally require working Git transport credentials (for example, `gh auth setup-git`). Empty repositories have no executable revision and are omitted.

## Namespaces and addresses

The authenticated GitHub owner is always available through `~`. Other owners must be explicitly trusted:

```console
zush namespace add Pathverse
zush namespace list
zush namespace remove Pathverse
```

Adding a namespace first asks GitHub to enumerate it. A successful enrollment trusts all repositories that are
visible under that owner, including repositories that become visible later. Removing it prevents new executions but
does not delete an existing Saucepan checkout.

After resolving the repository, Zush translates the script's dot path to repository-relative path segments. It first
accepts an exact executable file; otherwise it looks for exactly one of `.py`, `.ps1`, `.sh`, `.cmd`, or `.bat`.
Missing and ambiguous matches are errors.

## Arguments and structured input

Repeat `--arg` for ordinary arguments. Everything following `--` is passed through literally:

```console
zush ~tools:deploy --arg staging -- --force --var not-parsed
```

Structured options form one shallow JSON object:

```console
zush ~tools:deploy --map '{"retries": 2, "region": "east"}' --var region=west --casted bool+dry_run=false --casted float+ratio=1.5
```

Supported casts are `str`, `int`, `float`, `bool` (`true` or `false`), and `json`. Precedence is alias defaults,
then each `--map`, then `--var`, then `--casted`; replacement is shallow. When the object is nonempty, the child
receives its temporary JSON path in `ZUSH_INPUT_FILE`. The file is deleted after the child exits, and stdin remains
untouched.

## Aliases and `.zush`

The authenticated owner's optional GitHub repository named `.zush` may provide a read-only `map.toml`:

```toml
[commands.deploy]
target = { owner = "~", repo = "tools", path = "scripts.deploy" }
default_args = ["staging"]
default_map = { retries = 2, dry_run = false }

[namespaces.alice]
exclude = ["archive-*", "private-scripts"]
```

The `owner` value is `"~"` or an explicit GitHub owner. Exclusion patterns use case-sensitive shell-style matching
and prevent matching repositories from reaching Saucepan.

Local aliases overlay remote aliases without writing to `.zush`:

```console
zush alias bind ship ~tools:scripts.deploy
zush run ship --arg production
zush alias unbind ship
```

Binding replaces a remote alias locally. Unbinding records a local tombstone, so it can also hide a remote-only
alias. Local alias state and retained output bindings are separate from the remote `.zush` repository.

## Commands inside installed repositories

An installed repository can publish `.zush/map.toml` without a central alias:

```toml
[commands.deploy]
path = "scripts.deploy"
default_args = ["staging"]
default_map = { retries = 2 }
```

This selects `.zush/scripts/deploy.py` (or another supported, unambiguous script type).
Local maps accept paths within their own `.zush` directory. Cross-repository `target` records belong in the central map.

```console
zush commands
zush run alice/tools:deploy
zush run ~tools:deploy --arg production
zush run deploy
zush run deploy --no-first
```

`commands` lists provenance and qualified names from installed, visible, enrolled and non-excluded repositories.
It does not download every visible repository to search for commands. A qualified invocation may acquire that one
repository. The optional central `.zush` repository is loaded for global configuration as usual.

Unqualified names use **first match by default**: local aliases override central aliases, then repository commands
follow in canonical owner/repository order. `--no-first` fails on a collision and lists its candidates. An overridden
central alias and its local replacement count as one effective alias. An unbind tombstone hides the name across
unqualified discovery; a qualified invocation remains explicit. Arguments after `--` are passed to the script literally.
The existing direct address syntax (`zush ~tools:scripts.deploy`) continues to resolve relative to the repository root.

## Updates and retained state

Normal execution reuses an installed checkout and never updates it. Run `zush update` explicitly to refresh every
visible managed repository. By default local state lives in `~/.zush`; set `ZUSH_HOME` to relocate all Zush state or
`ZUSH_SAUCEPAN` to select a specific Saucepan executable.

The manager uses its normal user-level `.saucepan` root. Set `ZUSH_SAUCEPAN_ROOT` to use an explicitly initialized different store. Applications, scopes, credentials and keyring protection are optional Saucepan features and are not required by this launcher.

Bindings are written atomically under a bounded file lock. Selected and previous output generations stay pinned, so an update cannot remove files used by another Zush process. This deliberately consumes storage; automatic pin cleanup is not implemented. Failed updates preserve the previous selection. A lost response is reconciled on the next update using the saved operation identity, not a new request.

Earlier Zush state is unsupported. Choose a new `ZUSH_HOME` and reacquire repositories; no old state or store is automatically deleted. Recreate namespace enrollment and local aliases as needed.

## Development checks

```console
uv sync --locked
uv run python -m unittest discover -s tests
uv run ruff check src tests features
uv build
```

The unit suite skips real-manager integration unless `ZUSH_TEST_SAUCEPAN` names an absolute executable path.
Set it to a current Saucepan binary and rerun the suite to exercise local Git acquisition, central and repository
command maps, explicit updates, failed updates, and old-output retention. Tests initialize temporary stores and
leave the user's real store unchanged. Run each `features/<capability>` directory with `uv run behave` for the
behavior checks; the runtime capability also installs the wheel in a fresh Python 3.12 environment and checks
help/version without invoking the manager. Native script runners beyond Python require their respective platform.
