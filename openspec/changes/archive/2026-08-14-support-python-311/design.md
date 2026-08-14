## Context

Zush currently declares Python 3.14 even though its runtime code is standard-library-only and its newest required standard-library module is `tomllib`, introduced in Python 3.11. The package build, lock, Ruff target, developer interpreter pin, tests, and documentation must agree on one minimum.

## Goals / Non-Goals

**Goals:**

- Make Python 3.11 the single declared and verified minimum across package and development metadata.
- Prove the built wheel, rather than only the source checkout, starts on Python 3.11.
- Preserve the empty runtime dependency set.

**Non-Goals:**

- Support Python 3.10 or earlier.
- Add a `tomli` fallback or vendor another TOML parser.
- Change Zush command behavior, repository acquisition, or script runner semantics.
- Treat repository-local agent skill prose as executable product behavior.

## Decisions

### Use Python 3.11 as the compatibility floor

Set `requires-python`, `.python-version`, and Ruff's target to Python 3.11. This is the lowest standard-library-only option for the current code because configuration parsing imports `tomllib` directly. Python 3.10 plus `tomli` would widen the surface further but would reverse the accepted no-runtime-dependencies constraint.

### Verify the distribution boundary

Build the wheel with the declared backend, inspect its `Requires-Python` metadata, and run its console entry point in an isolated Python 3.11 environment. Retain the complete unit and capability suites to detect syntax or behavior regressions.

### Package three concise repository-local skills

Create separate setup, configuration, and usage skills under `/skills`. Each skill owns one task-oriented workflow, includes generated `agents/openai.yaml`, and references current Zush commands rather than copying implementation details. Validate each skill with the skill-creator validator.

## Risks / Trade-offs

- **A dependency or syntax feature may silently require a newer interpreter.** → Resolve and execute the full test and wheel gates explicitly on Python 3.11.
- **Three skills can duplicate command guidance.** → Give each a narrow responsibility and keep shared facts minimal.
- **Python 3.10 users remain unsupported.** → Preserve dependency simplicity and document why 3.11 is the compatibility floor.
