# runtime-compatibility Specification

## Purpose

Defines the oldest Python runtime on which Zush can be installed and exercised as a supported packaged application.

## Requirements

### Requirement: Python 3.11 is the minimum supported runtime
The Zush distribution SHALL declare Python 3.11 or newer and SHALL run its public CLI on Python 3.11 without requiring compatibility-only runtime dependencies.

#### Scenario: Install and run on Python 3.11
- **WHEN** the built Zush wheel is installed into an isolated Python 3.11 environment
- **THEN** `zush --version` starts successfully and reports the packaged version

#### Scenario: Reject an older Python runtime
- **WHEN** an installer evaluates the built Zush wheel for Python 3.10
- **THEN** the wheel metadata rejects that runtime as unsupported
