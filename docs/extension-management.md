# Management Extension Plan

This document is the implementation guide for building a separate extension-management package for zush.

Use this guide when you want to support workflows such as:

- install an extension from a registry entry
- install an extension from a GitHub repository
- resolve private repositories inside a GitHub organization
- report install status, available updates, and configured sources
- offer scoop-like extension management without turning zush core into a package manager

## Goal

Build a separate package that manages remote extension sources and local installation state, while zush continues to do local discovery, loading, and runtime integration.

## Non-Negotiable Boundary

Keep these concerns separate.

zush core owns:

- discover installed extensions from local environments
- load one concrete extension package from disk
- mount commands, hooks, providers, and services into the live CLI tree
- expose controlled `self` commands and diagnostics

The management extension owns:

- search remote registries or GitHub sources
- authenticate to private registries or private GitHub repositories
- clone, download, install, update, and remove extensions
- track install metadata and local managed state
- expose management commands such as `install`, `status`, `search`, `update`, and `sources`

Do not move install behavior into discovery providers or `pluginloader`.

## Responsibility Rules

Use these rules when deciding where code belongs.

- discovery provider: answers "what is installed here?"
- pluginloader: answers "how do I load this package?"
- management extension: answers "how do I fetch, install, update, and track this package?"

If a feature needs GitHub auth, registry access, cloning, archive download, version resolution, update policy, or install metadata, it belongs in the management extension.

## Recommended Package Shape

Build the manager as a separate package with four internal areas.

1. Registry client

- reads one or more registry indexes
- can query GitHub APIs or registry manifests
- resolves extension identifiers to install targets

2. Installer

- clones repositories, downloads archives, or installs packaged extensions
- writes into a local managed extensions directory
- records source URL, resolved revision, and install time

3. Local state store

- records what is installed
- tracks versions, revisions, source type, and update status
- keeps manager-specific metadata out of zush core state

4. zush integration layer

- registers controlled `self` commands
- updates zush config or managed env paths when needed
- reports diagnostics and status in zush-native terms

## Recommended Local Layout

Install managed extensions into local directories that zush can already scan.

Suggested layout:

```text
~/.zush/
  extensions/
    gh-org/
      zush_demo/
        __zush__.py
        ...
    registry/
      zush_other/
        __zush__.py
        ...
  ext-state.json
```

Guidelines:

- zush should scan `~/.zush/extensions/gh-org` and `~/.zush/extensions/registry` as normal env roots
- the management extension should own `ext-state.json`
- installed extension packages must still contain `__zush__.py` at the package root
- the manager must not require zush core to understand remote registry metadata

## Command Surface Guidelines

The management extension should integrate through controlled `self` commands.

Recommended first commands:

- `zush self install <extension>`
- `zush self uninstall <extension>`
- `zush self status`

Recommended next commands:

- `zush self update <extension>`
- `zush self search <query>`
- `zush self sources`

Do not try to extend the normal dotted command tree with `self.*` keys. Use the controlled self-command surface that zush already exposes.

## Extension Identity Guidelines

Treat extension identity as a stable logical ID, not only a folder name.

Recommended rule:

- the management extension keeps a stable `extension_id`
- the installed directory name may match that ID for compatibility
- zush may still fall back to package-path naming when explicit identity is absent

Practical implication:

- manager state should be keyed by `extension_id`
- user-facing commands should use `extension_id`
- install layout may use the same value to minimize surprises

## Supported Source Types

The first manager should support more than one source type without requiring zush core changes.

### Registry-backed source

Requirements:

- resolve extension ID from a manifest index
- map extension ID to a downloadable archive or repository reference
- install the resolved package into the local managed directory

### GitHub-backed source

Requirements:

- resolve organization repositories directly through the GitHub API
- optionally filter by topic, naming rule, or manifest file
- support private repositories using a PAT, GitHub App token, or gh CLI auth

## Authentication Guidelines

Keep authentication outside zush core.

Recommended policy:

- GitHub auth should be handled by the management extension
- credentials should be sourced from environment variables, a secure token store, or an existing authenticated CLI flow such as `gh`
- zush core should not persist or interpret registry credentials

## Current zush Surface You Can Rely On

The current zush surface is already enough to support an external manager package.

You can rely on:

- controlled `self` command registration
- discovery diagnostics
- command conflict diagnostics
- injectable storage
- provider-based discovery seams
- extension toggling via `disabled_extensions`

That means the manager can integrate today without waiting for zush to become a package manager.

## What Must Stay Out of zush Core

Do not move these concerns into zush core:

- GitHub authentication
- remote registry fetching
- install metadata state
- repo cloning or archive download
- update policy resolution
- private source credential handling

If a feature requires those behaviors, keep it in the manager package.

## Implementation Phases

Build the manager in phases.

### Phase 1: Minimal working manager

Deliver this first:

1. Maintain one managed install directory under `~/.zush/extensions`.
2. Register `self install`, `self uninstall`, and `self status`.
3. Install from direct GitHub repository URLs or a GitHub organization query.
4. Ensure installed extensions land in a layout zush already discovers.
5. Record install metadata in a manager-owned state file.

Success condition:

- a user can install an extension from GitHub and immediately run it through zush without manual filesystem setup

### Phase 2: Registry support

Deliver next:

1. Add registry manifest resolution.
2. Add `self search` and `self sources`.
3. Support registry refresh and source add or remove.

Success condition:

- a user can search and install from one or more configured registries

### Phase 3: Update and policy features

Deliver after the basics work:

1. Add `self update`.
2. Track revisions and available updates.
3. Add compatibility checks against zush versions if needed.

Success condition:

- a user can inspect outdated extensions and update them safely

## Implementation Checklist

Use this checklist when building the first version.

- define the manager package boundary
- define the local install root
- define the manager-owned state file schema
- implement GitHub source resolution
- implement install into zush-compatible package layout
- implement `self install`
- implement `self uninstall`
- implement `self status`
- ensure zush env scanning can see the managed install root
- add diagnostics for install failures and invalid extension layout

## Validation Checklist

Before calling the manager viable, verify all of these.

- installed extensions are discoverable by zush without custom patches to zush core
- installed package directories contain `__zush__.py` at the package root
- uninstall removes the local install and updates manager state
- status shows installed extensions even if remote sources are unavailable
- private GitHub access failures are surfaced clearly by the manager
- zush diagnostics remain focused on discovery and loading, not remote install logic

## Nice-to-Have Future Improvements

These are optional, not prerequisites.

- explicit provider selection in zush config
- first-class extension identity in plugin metadata
- signed registry manifests
- lockfile-style pinning for installed extensions
- extension compatibility checks against zush versions

## Bottom Line

Build the management system as a separate package.

- keep zush as the discovery, loading, and runtime host
- put installation, registry lookup, and GitHub integration in the management extension
- install extensions into local env roots that zush can already scan
- expose manager operations through controlled `self` commands

That is the recommended way to get scoop-like behavior without making zush core responsible for package management.