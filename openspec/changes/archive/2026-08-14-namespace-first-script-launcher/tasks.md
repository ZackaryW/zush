## 1. Clarification and project gates

- [x] 1.1 Reconcile the namespace-first launcher contract against the separate plugin-platform evidence
- [x] 1.2 Confirm the clean-break boundary, address grammar, trust scope, runners, structured transport, configuration layering, and explicit-update policy
- [x] 1.3 Create and strictly validate the proposal, five capability deltas, design, and implementation ledger

## 2. Behavior shaping

- [x] 2.1 Create an independently runnable `features/namespace-discovery/` root covering its accepted public requirements
- [x] 2.2 Create an independently runnable `features/repository-materialization/` root covering its accepted public requirements
- [x] 2.3 Create an independently runnable `features/script-execution/` root covering its accepted public requirements
- [x] 2.4 Create an independently runnable `features/structured-input/` root covering its accepted public requirements
- [x] 2.5 Create an independently runnable `features/command-aliases/` root covering its accepted public requirements
- [x] 2.6 Add shared lifecycle and public CLI verification support under `features/support/` with thin capability bindings
- [x] 2.7 Parse every capability root independently and verify complete delta-scenario traceability

## 3. Utility planning and project setup

- [x] 3.1 Record a disposable signature-level utility plan after Ponytail assessment
- [x] 3.2 Configure supported Python, lock, build backend, development test, Behave, lint, and format gates
- [x] 3.3 Establish environment-overridable local state and subprocess seams for isolated tests

## 4. Address, namespace, and inventory utilities

- [x] 4.1 Prove address parsing, malformed syntax, and current-owner expansion RED, then implement the parser
- [x] 4.2 Prove namespace persistence, enrollment, removal, and authorization RED, then implement local namespace state
- [x] 4.3 Prove repository enumeration parsing and exclusions RED, then implement the GitHub boundary
- [x] 4.4 Prove deterministic ref-pinned bucket generation RED, then implement local acquisition-index serialization

## 5. Configuration and invocation utilities

- [x] 5.1 Prove TOML alias parsing, typed defaults, local precedence, and tombstones RED, then implement configuration loading and overlay
- [x] 5.2 Prove bind/unbind persistence RED, then implement recoverable local overlay writes
- [x] 5.3 Prove JSON-map, string assignment, cast matrix, shallow precedence, and invalid-input RED, then implement structured values
- [x] 5.4 Prove temporary JSON environment and cleanup RED, then implement the structured-input context

## 6. Script and Saucepan utilities

- [x] 6.1 Prove exact, inferred, missing, and ambiguous script-selection RED, then implement deterministic resolution
- [x] 6.2 Prove runner argv for Python, PowerShell, POSIX shell, Windows command files, and direct executables RED, then implement native runner selection
- [x] 6.3 Prove Saucepan index registration, provenance lookup, install reuse, failure handling, and explicit update RED, then implement the subprocess adapter
- [x] 6.4 Run all focused utility tests GREEN and remove the disposable utility plan

## 7. Public CLI wiring

- [x] 7.1 Wire `namespace add`, `namespace list`, and `namespace remove` through GitHub validation and local state
- [x] 7.2 Wire direct address execution through namespace discovery, generated inventory, Saucepan materialization, local script resolution, structured input, and transparent process execution
- [x] 7.3 Wire `alias bind`, `alias unbind`, and `run` through remote configuration plus the local overlay
- [x] 7.4 Wire explicit `update` through refreshed inventories and provenance-selected Saucepan entries
- [x] 7.5 Return stable user-facing failures and preserve child exit status

## 8. Verification and documentation

- [x] 8.1 Run each capability-owned Behave root independently through the installed CLI
- [x] 8.2 Run focused and complete unit tests and the complete Behave suite
- [x] 8.3 Verify lock consistency, supported Python, Ruff lint and format, and a clean wheel and source build
- [x] 8.4 Validate an isolated built-wheel CLI and strict OpenSpec change
- [x] 8.5 Document addresses, namespaces, Saucepan behavior, aliases, structured input, exclusions, updates, and external runtime requirements

## 9. Specification formation and finalization

- [x] 9.1 Reconcile mature green behavior into canonical capability specifications
- [x] 9.2 Inspect and reconcile any retained OpenLease successor cohorts (none are retained in this repository)
- [x] 9.3 Archive the completed OpenSpec change only after the full verification set is green
- [x] 9.4 Create no commit unless separately and explicitly authorized (no commit was authorized or created)

## 10. ZPP stage outcomes

- [x] 10.1 `clarify` — completed: the owner-confirmed proposal, five capability deltas, design, and task agreement are coherent
- [x] 10.2 `shape` — completed: five capability roots parse independently and trace all 45 accepted delta scenarios
- [x] 10.3 `plan-utilities` — completed: the disposable gate defines eight ordered standard-library and Saucepan seams with focused RED targets
- [x] 10.4 `mature-utilities` — completed: 26 focused tests, Ruff lint, and Ruff format are green after relevant fail-first evidence
- [x] 10.5 `wire` — completed: the public `zush` CLI and all five independently runnable capability roots are green
- [x] 10.6 `form-specs` — completed: five canonical capability specs are strict-valid and no retained OpenLease cohorts exist
- [x] 10.7 `finalize` — completed: all declared gates, clean artifacts, isolated wheel execution, strict specs, and archival are green
