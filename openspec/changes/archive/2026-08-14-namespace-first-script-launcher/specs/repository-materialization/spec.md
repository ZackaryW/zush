## Purpose

Defines how Zush converts visible GitHub repositories into Saucepan-managed working copies without requiring repository-authored acquisition metadata.

## ADDED Requirements

### Requirement: Namespace inventory supplies acquisition metadata
Zush SHALL derive a private local Saucepan index from GitHub repository identity, description, and current default-branch commit. Each generated entry SHALL carry a unique acquisition identity, the repository target, a manifest, and the exact commit as its ref, and SHALL NOT carry command-tree declarations.

#### Scenario: Manifest-less repository is inventoried
- **WHEN** GitHub enumeration returns a repository that has no Saucepan manifest
- **THEN** Zush generates sufficient local index metadata for Saucepan to install the repository at the enumerated commit

#### Scenario: Generated index remains local
- **WHEN** Zush refreshes namespace inventory
- **THEN** the generated index is written only to Zush-managed local state and is not committed to the user's `.zush` repository

### Requirement: Saucepan owns repository lifecycle
Zush SHALL delegate repository install, update, path lookup, and uninstall state to Saucepan and SHALL NOT maintain an independent clone or pull implementation.

#### Scenario: First invocation materializes a repository
- **WHEN** a valid address names a visible repository that Saucepan has not installed
- **THEN** Zush asks Saucepan to install the repository and resolves the script from the resulting managed path

#### Scenario: Existing installation is reused
- **WHEN** a valid address names a repository already managed by Saucepan
- **THEN** Zush resolves its current Saucepan path without cloning it again

### Requirement: Installed identity follows provenance
Zush SHALL locate an installed repository by its recorded `owner/repo` provenance rather than assuming the repository target equals the installed manifest name.

#### Scenario: Repository manifest chooses another name
- **WHEN** a repository-owned Saucepan manifest overrides the generated index and declares a different installed name
- **THEN** Zush still locates the checkout through its repository provenance

### Requirement: Updates are explicit
Zush SHALL update managed repositories only when the user invokes the Zush update command. Ordinary script execution SHALL NOT refresh or pull an existing checkout.

#### Scenario: Execute an installed repository
- **WHEN** the user invokes a script from an existing managed checkout
- **THEN** Zush uses the current checkout without contacting Saucepan for an update

#### Scenario: Explicit update
- **WHEN** the user invokes `zush update`
- **THEN** Zush refreshes visible namespace metadata and asks Saucepan to update each installed remote repository still represented by that inventory

### Requirement: Materialization failures preserve safety
Zush SHALL surface Saucepan acquisition failures and SHALL not execute a path from a partial or unresolved checkout.

#### Scenario: Saucepan installation fails
- **WHEN** Saucepan cannot install the resolved repository
- **THEN** Zush returns a failure and executes no script
