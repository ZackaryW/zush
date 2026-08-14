# namespace-discovery Specification

## Purpose

Defines which GitHub repository namespaces Zush exposes and how authentication, explicit trust, and exclusions constrain that surface.

## Requirements

### Requirement: Authenticated owner shorthand
Zush SHALL resolve `~` to the login returned by the active GitHub CLI authentication and SHALL expose repositories owned by that login which the active credential can enumerate.

#### Scenario: Resolve the current owner
- **WHEN** an authenticated user invokes an address beginning with `~`
- **THEN** Zush resolves the repository within that user's owned repository namespace

#### Scenario: GitHub authentication is unavailable
- **WHEN** Zush cannot obtain the active GitHub login
- **THEN** Zush fails before repository acquisition and explains that GitHub authentication is required

### Requirement: Explicit namespace enrollment grants trust
Zush SHALL provide `namespace add <owner>` to validate that an owner can be enumerated, persist that owner, and authorize discovery and execution of every visible current or future repository under it.

#### Scenario: Add an accessible namespace
- **WHEN** the user adds an owner that the active GitHub credential can enumerate
- **THEN** Zush persists the owner and accepts addresses beneath it without a later trust prompt

#### Scenario: Added namespace gains a repository
- **WHEN** a repository becomes visible beneath an already-added owner
- **THEN** the repository becomes addressable on the next namespace refresh without another enrollment decision

#### Scenario: Add an inaccessible namespace
- **WHEN** GitHub cannot enumerate the requested owner with the active credential
- **THEN** Zush reports the failure and does not persist or trust the owner

### Requirement: Namespace enrollment is inspectable and removable
Zush SHALL list added namespaces and SHALL remove an added namespace without deleting already-managed repository checkouts.

#### Scenario: Remove a namespace
- **WHEN** the user removes an added owner
- **THEN** new addresses beneath that owner are rejected while existing managed source state remains intact

### Requirement: Repository exclusions constrain discovery
Zush SHALL apply repository-name glob exclusions declared for an owner in the optional `.zush` configuration before presenting or materializing that owner's repositories.

#### Scenario: Excluded repository
- **WHEN** an address names a repository matched by an exclusion for its owner
- **THEN** Zush reports that the repository is excluded and does not ask Saucepan to install it

#### Scenario: Unmatched repository
- **WHEN** a repository is visible and no exclusion matches it
- **THEN** the repository remains addressable
