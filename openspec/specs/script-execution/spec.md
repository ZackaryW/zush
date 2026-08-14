# script-execution Specification

## Purpose

Defines stable repository-script addressing, deterministic local script selection, native runner behavior, and transparent process results.

## Requirements

### Requirement: Repository and script boundaries are explicit
Zush SHALL accept direct addresses as `~repo:<dot-path>` for the authenticated owner and `owner/repo:<dot-path>` for an added namespace. The colon SHALL separate repository identity from script path even when repository names contain dots.

#### Scenario: Current-owner address
- **WHEN** the user invokes `~tools:release.publish`
- **THEN** Zush resolves repository `tools` under the authenticated owner and local base path `release/publish`

#### Scenario: Added-owner address
- **WHEN** the user invokes `Pathverse/scripts.tools:release.publish`
- **THEN** Zush resolves repository `scripts.tools` under added owner `Pathverse`

#### Scenario: Malformed address
- **WHEN** an address omits its repository, colon, or script path
- **THEN** Zush rejects it before acquisition and reports the accepted forms

### Requirement: Script selection is deterministic
For a dot path, Zush SHALL first consider an exact repository-relative file and then the base path with supported suffixes `.py`, `.ps1`, `.sh`, `.cmd`, and `.bat`. Zush SHALL execute only when exactly one supported candidate exists; an exact directly executable file SHALL be a supported candidate.

#### Scenario: One inferred script
- **WHEN** `tasks/cleanup.py` is the only supported candidate for dot path `tasks.cleanup`
- **THEN** Zush selects that file

#### Scenario: Exact executable file
- **WHEN** the exact base path is a directly executable file
- **THEN** Zush selects it without adding a suffix

#### Scenario: Multiple inferred scripts
- **WHEN** both `tasks/cleanup.py` and `tasks/cleanup.sh` exist
- **THEN** Zush reports an ambiguity naming both files and executes neither

#### Scenario: Unknown script
- **WHEN** no supported candidate exists after the repository is available
- **THEN** Zush reports an unknown script and executes nothing

### Requirement: Supported scripts use native runners
Zush SHALL run `.py` with the active Python interpreter, `.ps1` with an available PowerShell, `.sh` with an available POSIX shell, `.cmd` and `.bat` with the Windows command processor, and exact executable files directly. If the required native runner is unavailable, Zush SHALL fail before starting the script.

#### Scenario: Python script
- **WHEN** Zush selects a `.py` script
- **THEN** it launches the script through the active Python interpreter

#### Scenario: Required runner is missing
- **WHEN** the selected script type requires a runner that is not available
- **THEN** Zush reports the missing runner and does not execute the script

### Requirement: Script arguments and results remain transparent
Zush SHALL append every repeated `--arg` value followed by all tokens after `--`, preserving their order, and SHALL inherit the script's standard input, output, and error streams. Zush SHALL return the script process exit status.

#### Scenario: Raw arguments
- **WHEN** a script invocation supplies `--arg first -- --flag second`
- **THEN** the script receives `first`, `--flag`, and `second` in that order

#### Scenario: Script failure
- **WHEN** the executed script exits with a nonzero status
- **THEN** Zush returns the same status without converting it to a successful invocation
