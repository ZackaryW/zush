# repository-command-discovery Specification

## Purpose

Expose commands from repository-local `.zush` folders alongside central and local aliases with predictable selection and retained execution paths.

## Requirements

### Requirement: Installed repository command maps are discoverable
Zush SHALL discover `.zush/map.toml` in installed eligible repository outputs. Its `[commands.<name>]` records SHALL declare a dot `path` relative to `.zush`, optional `default_args`, and optional typed `default_map`. Zush SHALL list qualified names and provenance through `zush commands` without materializing every visible repository. Missing maps SHALL be treated as no commands; malformed maps SHALL identify the offending repository and path.

#### Scenario: Installed repository has commands
- **WHEN** an eligible installed repository contains a valid local command map
- **THEN** its commands appear with repository-qualified names and source provenance

#### Scenario: Repository is not installed
- **WHEN** Zush lists unqualified command candidates
- **THEN** it does not acquire that repository merely to inspect a possible `.zush` folder

### Requirement: Qualified command execution is explicit
`zush run owner/repo:command` and `zush run ~repo:command` SHALL select the named repository-local command after the existing namespace, visibility, and exclusion checks. An explicit qualified request MAY materialize that one repository. The command SHALL use the existing argument, structured-input, runner, and exit-status behavior; its resolved path SHALL remain within the retained `.zush` directory, including after symlink resolution.

#### Scenario: Qualified local command
- **WHEN** `zush run alice/tools:deploy` selects a map record with `path = "scripts.deploy"`
- **THEN** Zush runs the selected `.zush/scripts/deploy` candidate from the retained tools output with its defaults and invocation overrides

#### Scenario: Escaping command path
- **WHEN** the selected path or symlink resolves outside the output's `.zush` directory
- **THEN** Zush rejects the command before execution

### Requirement: Unqualified names use deterministic first match
Unqualified `zush run NAME` SHALL use first match by default: effective local/central aliases first, then repository-local candidates sorted by canonical owner/repository. Existing local overrides and tombstones SHALL remain effective; a tombstone SHALL suppress the unqualified name across layers. `--no-first` SHALL fail on multiple visible effective candidates and report their qualified provenance. A local override and the central alias it replaces SHALL count as one candidate.

#### Scenario: Default collision handling
- **WHEN** two installed repositories expose the same unqualified command and no global alias wins
- **THEN** Zush selects the first repository in canonical order independently of filesystem or GitHub enumeration order

#### Scenario: Strict collision handling
- **WHEN** the user supplies `--no-first` and more than one effective candidate matches
- **THEN** Zush reports the collision and executes nothing

#### Scenario: Qualified command bypasses unqualified ambiguity
- **WHEN** the user specifies a qualified repository command
- **THEN** other repositories' same-named commands do not affect selection
