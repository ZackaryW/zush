---
name: zush-setup
description: Install, upgrade, and verify the Zush GitHub-backed script launcher and its external prerequisites. Use when an agent needs to prepare Zush on a machine, confirm GitHub authentication, select local state locations, or diagnose an incomplete installation.
---

# Set up Zush

## Establish the environment

1. Confirm Python 3.12 or newer with `python --version` or `uv python find '>=3.12'`.
2. Confirm Git and GitHub CLI are available with `git --version` and `gh --version`.
3. Check the active credential with `gh auth status`. Do not initiate or replace authentication unless the user asks.
4. From a Zush source checkout, install with `uv tool install .`. Use the user's requested installer if they name another supported workflow.
5. Verify the installed boundary with `zush --version` and `zush --help`.

Zush has no Python runtime dependencies. It uses external `gh`, Git, Saucepan, and the native runner required by each selected script.

## Explain Saucepan setup

Zush uses the external Saucepan Python SDK and an already installed Saucepan 0.9.x manager. Require `saucepan init` before use; never download or initialize a manager implicitly. `ZUSH_SAUCEPAN` selects the executable and `ZUSH_SAUCEPAN_ROOT` selects an initialized store.

Do not configure a second clone manager or write Saucepan manifests into target repositories merely to make Zush work.

## Select local state

Zush defaults to `~/.zush`. Set `ZUSH_HOME` before invoking Zush when state must live elsewhere:

```powershell
$env:ZUSH_HOME = "D:\zush-state"
zush namespace list
```

The directory is created lazily. It can contain namespace and alias state, the generated local index, Saucepan state, and the acquired Saucepan binary. Distinguish this local directory from the optional read-only GitHub repository named `.zush`.

## Diagnose setup failures

- For authentication errors, run `gh auth status` and preserve its diagnostic output.
- For Saucepan acquisition errors, check `ZUSH_SAUCEPAN`, platform support, and network access.
- For runner errors, install or select the native runner required by `.ps1`, `.sh`, `.cmd`, or `.bat` scripts.
- For Python compatibility errors, inspect the installed distribution metadata and require Python 3.12 or newer.

Do not execute a repository script merely to prove installation; `zush --version` is the safe setup check.

