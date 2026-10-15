# repository-materialization Specification

## Purpose

Defines how Zush converts visible GitHub repositories into Saucepan-managed working copies without requiring repository-authored acquisition metadata.

## Requirements

### Requirement: Saucepan owns repository lifecycle
Zush SHALL delegate repository retrieval, output preparation, and retention to the current Saucepan SDK and SHALL NOT maintain an independent clone, pull, or binary download implementation. Existing managed outputs SHALL be located through canonical repository provenance and selected output receipts, independent of repository-authored manifests.

#### Scenario: First invocation materializes a repository
- **WHEN** a valid address names a visible repository without a selected output
- **THEN** Zush prepares and retains the exact enumerated commit through Saucepan before resolving its path

#### Scenario: Existing installation is reused
- **WHEN** a valid address names a repository with a selected managed output
- **THEN** Zush uses that output without cloning or preparing a new revision

### Requirement: Updates are explicit
Zush SHALL update selected outputs only on first materialization or explicit `zush update`. Ordinary execution SHALL NOT refresh an existing output. Updates SHALL be published per repository only after receiving and validating a retained output; no all-repository atomicity is promised.

#### Scenario: Execute an installed repository
- **WHEN** the user invokes a script from an existing managed checkout
- **THEN** Zush uses the selected immutable output without requesting an update

#### Scenario: Explicit update
- **WHEN** the user invokes `zush update`
- **THEN** Zush refreshes visible namespace metadata and prepares new selections for installed repositories still visible, enrolled, and non-excluded

### Requirement: Materialization failures preserve safety
Zush SHALL surface structured acquisition failures, SHALL never execute a partial or unresolved output, and SHALL preserve the previous selection on failed update. Potentially committed operations SHALL be reconciled using their original operation identity before any replacement mutation.

#### Scenario: Saucepan installation fails
- **WHEN** Saucepan cannot prepare the resolved repository
- **THEN** Zush returns a failure and executes no script

#### Scenario: Update fails with an existing selection
- **WHEN** an update cannot produce a validated retained output
- **THEN** the update reports failure and the previous selection remains usable

#### Scenario: Mutation receipt is lost
- **WHEN** transport ends after a preparation may have committed
- **THEN** Zush reconciles the original operation rather than issuing a new operation identity or executing an uncertain path

### Requirement: Repository outputs remain retained for readers
Zush SHALL retain selected and previously published generations across processes so script execution and configuration reads cannot lose files during an update. Mutations of shared consumer state SHALL be serialized with bounded waits, and published bindings SHALL be atomic.

#### Scenario: Update overlaps script execution
- **WHEN** one process updates a repository while another uses its previous output
- **THEN** the previous output remains readable and the new selection identifies a separate immutable output

### Requirement: Basic operation requires no protected application
Zush SHALL support its normal launcher flow without application registration, credentials, keyring configuration, or an application scope. It SHALL use the current external manager's standard root unless explicitly overridden.

#### Scenario: Unprotected local use
- **WHEN** an initialized current manager is available with no protected application configuration
- **THEN** Zush can prepare, retain, and execute eligible repository content

### Requirement: Profile expansion belongs to the manager
Zush SHALL obtain `explicit-update` through the public SDK, explicitly register the returned catalog, and attach combined immutable policy UUID references when preparing a new exact-commit selection. Pending operations SHALL preserve expanded definitions and refs across recovery. Ordinary selected-path reads SHALL NOT re-expand profiles. Pins and application setup SHALL remain independent.

#### Scenario: Recovery after a recipe changes
- **WHEN** a preparation receipt is lost and a later profile preview would differ
- **THEN** recovery uses the original saved catalog and refs without adopting the later recipe
