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

Zush requires Python 3.14 or newer, [GitHub CLI](https://cli.github.com/) (`gh`), and a working `gh auth login`.
Script execution additionally requires the native runner for the selected file type.

```console
uv tool install .
zush --version
```

Zush uses Saucepan v0.3 as its repository source manager. An installed `saucepan` is reused; otherwise the pinned
binary is acquired on first use and stored under Zush's local state directory. Saucepan owns checkout installation,
provenance, paths, and updates. Zush only generates a private, ref-pinned acquisition index; it does not generate a
second command tree.

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
alias. Local alias state and the generated Saucepan index are separate from the remote `.zush` repository.

## Updates and state

Normal execution reuses an installed checkout and never updates it. Run `zush update` explicitly to refresh every
visible managed repository. By default local state lives in `~/.zush`; set `ZUSH_HOME` to relocate all Zush state or
`ZUSH_SAUCEPAN` to select a specific Saucepan executable.
