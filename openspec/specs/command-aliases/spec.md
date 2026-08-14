# command-aliases Specification

## Purpose

Defines portable read-only aliases from the user's `.zush` repository and locally mutable overlay bindings with deterministic expansion behavior.

## Requirements

### Requirement: Optional remote configuration is read-only
When the authenticated user owns a visible repository named `.zush`, Zush SHALL load its alias and exclusion configuration from `map.toml` through a Saucepan-managed checkout. Zush SHALL NOT create, commit, or push that repository during configuration or alias operations.

#### Scenario: Remote configuration exists
- **WHEN** the authenticated user's `.zush` repository contains a valid `map.toml`
- **THEN** its aliases and exclusions are available to Zush

#### Scenario: Remote configuration is absent
- **WHEN** no `.zush` repository is visible
- **THEN** Zush continues with local configuration only

#### Scenario: Invalid remote configuration
- **WHEN** remote `map.toml` is invalid
- **THEN** Zush reports the configuration error and does not execute an affected alias

### Requirement: Alias records have a stable TOML shape
`map.toml` SHALL declare aliases beneath `[commands.<name>]`. Each alias SHALL contain a target with `owner`, `repo`, and `path`, and MAY contain `default_args` and `default_map`.

#### Scenario: Complete alias
- **WHEN** an alias record supplies a valid target, default arguments, and default map
- **THEN** Zush loads all three components without converting typed TOML default-map values to strings

### Requirement: Local bindings overlay remote aliases
Zush SHALL persist local alias bindings separately from the read-only remote configuration. A local binding SHALL replace a remote alias of the same name, and a local unbind SHALL be able to hide a remote-only alias without changing the remote repository.

#### Scenario: Bind a local alias
- **WHEN** the user runs `zush alias bind <name> <target>`
- **THEN** a parsed local binding is persisted and becomes available through `zush run <name>`

#### Scenario: Override a remote alias
- **WHEN** a local binding and remote configuration define the same alias name
- **THEN** the local binding is used

#### Scenario: Unbind a remote-only alias
- **WHEN** the user unbinds an alias supplied only by remote configuration
- **THEN** a local tombstone hides it and the remote repository remains unchanged

### Requirement: Alias execution uses the direct-address pipeline
`zush run <name>` SHALL expand the selected alias into its physical target and invoke the same namespace, materialization, script-resolution, structured-input, and execution pipeline used by a direct address.

#### Scenario: Execute an alias
- **WHEN** an alias targets `~tools:release.publish`
- **THEN** Zush applies its defaults and executes that physical target through the direct-address pipeline

#### Scenario: Unknown alias
- **WHEN** the user runs an alias absent from the merged configuration
- **THEN** Zush reports an unknown alias and performs no repository acquisition

### Requirement: Explicit arguments follow alias defaults
Alias `default_args` SHALL precede repeated invocation `--arg` values and tokens following `--`. Invocation structured values SHALL overlay `default_map` according to the structured-input precedence contract.

#### Scenario: Alias arguments are extended
- **WHEN** an alias has default argument `base` and the invocation supplies `--arg extra -- --flag`
- **THEN** the script receives `base`, `extra`, and `--flag` in that order
