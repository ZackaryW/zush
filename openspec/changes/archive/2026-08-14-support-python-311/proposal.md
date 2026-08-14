## Why

Requiring Python 3.14 unnecessarily limits where Zush can be installed even though its implementation only needs standard-library features available in Python 3.11. Supporting Python 3.11 broadens the usable platform surface without adding runtime dependencies.

## What Changes

- Lower the packaged minimum Python version and repository interpreter pin from 3.14 to 3.11.
- Align linting, locking, testing, and package metadata with Python 3.11.
- Prove the complete CLI and packaged wheel remain functional on Python 3.11.
- Add repository-local agent skills for Zush setup, configuration, and usage as artifact-only supporting guidance.

## Capabilities

### New Capabilities

- `runtime-compatibility`: Defines the minimum supported Python runtime and the compatibility evidence required at that boundary.

### Modified Capabilities

None.

## Impact

This affects `pyproject.toml`, `.python-version`, `uv.lock`, compatibility verification, README requirements, and repository-local skills under `/skills`. Runtime dependencies remain empty; Python versions earlier than 3.11 remain unsupported because Zush uses the standard-library `tomllib` module.
