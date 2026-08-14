# structured-input Specification

## Purpose

Defines optional typed invocation data that remains independent of script discovery and preserves ordinary stdin and raw-argument behavior.

## Requirements

### Requirement: Invocation values form one object
Zush SHALL build an optional object using alias `default_map` first, each `--map` JSON object second, and `--var` plus `--casted` assignments last. Later layers SHALL replace earlier values at the same top-level key without recursively merging nested objects.

#### Scenario: Invocation value overrides alias default
- **WHEN** an alias default map sets `region` and the invocation sets `region` with `--var`
- **THEN** the invocation string value is present in the final object

#### Scenario: Map replacement is shallow
- **WHEN** a later layer supplies an object at a key already containing an object
- **THEN** the later object replaces the earlier object at that key

### Requirement: String and casted assignments are validated
`--var` SHALL accept `key=value` as a string. `--casted` SHALL accept `type+key=value` for `str`, `int`, `float`, `bool`, and `json`, preserving the resulting JSON type. Invalid keys, types, or values SHALL fail before script execution.

#### Scenario: Float assignment
- **WHEN** the invocation includes `--casted float+threshold=1.5`
- **THEN** the final object contains JSON number `1.5` at `threshold`

#### Scenario: Boolean assignment
- **WHEN** the invocation includes `--casted bool+enabled=false`
- **THEN** the final object contains JSON boolean `false` at `enabled`

#### Scenario: Invalid cast
- **WHEN** a value cannot be converted to its declared type
- **THEN** Zush reports the invalid assignment and does not execute the script

### Requirement: Map input must be a JSON object
Each `--map` value SHALL parse as JSON and SHALL have an object at its root.

#### Scenario: Non-object map
- **WHEN** `--map` contains a JSON array or scalar
- **THEN** Zush rejects it and does not execute the script

### Requirement: Typed input travels through a temporary JSON file
When the final object is nonempty, Zush SHALL serialize it as UTF-8 JSON with typed fields preserved, expose its path to the child as `ZUSH_INPUT_FILE`, leave stdin inherited, and remove the temporary file after the child exits. When the object is empty, Zush SHALL not set `ZUSH_INPUT_FILE` for the child.

#### Scenario: Script reads structured input
- **WHEN** a script is invoked with structured values
- **THEN** it can read the complete typed object from the file named by `ZUSH_INPUT_FILE`

#### Scenario: Temporary input cleanup
- **WHEN** the child exits successfully or unsuccessfully
- **THEN** Zush removes the temporary JSON file
