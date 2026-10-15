## REMOVED Requirements

### Requirement: Python 3.11 is the minimum supported runtime
**Reason**: The current external SDK requires Python 3.12.
**Migration**: Install Python 3.12 or newer and reinstall Zush with its external SDK dependency.

## ADDED Requirements

### Requirement: Python 3.12 is the minimum supported runtime
The distribution SHALL require Python 3.12 or newer, SHALL install its SDK as an external dependency from a reproducible source, and SHALL contain no vendored Saucepan implementation or private binary downloader.

#### Scenario: Install and run on Python 3.12
- **WHEN** the built wheel is installed in a fresh Python 3.12 environment with its declared dependencies
- **THEN** `zush --version` and `zush --help` run without initializing Saucepan or contacting GitHub

#### Scenario: Reject an older runtime
- **WHEN** an installer evaluates the wheel on Python 3.11
- **THEN** its metadata rejects the unsupported runtime

### Requirement: Manager setup is explicit
Zush SHALL use an externally installed current Saucepan executable from the configured override or PATH, SHALL diagnose unsupported or unavailable managers and uninitialized roots, and SHALL NOT silently download a binary or initialize a store.

#### Scenario: Manager is missing
- **WHEN** a materialization operation needs Saucepan but no supported executable is available
- **THEN** Zush reports the required setup and performs no binary download
