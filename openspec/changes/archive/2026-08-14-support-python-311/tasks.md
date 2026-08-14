## 1. Clarification and behavior shaping

- [x] 1.1 Record the owner-confirmed Python 3.11 floor, zero-runtime-dependency constraint, and repository-local skill location
- [x] 1.2 Strictly validate the proposal, runtime-compatibility delta, design, and task agreement
- [x] 1.3 Create an independently runnable `features/runtime-compatibility/` root for the accepted package boundary

## 2. Runtime compatibility

- [x] 2.1 Update the project runtime declaration, developer interpreter pin, and Ruff target to Python 3.11
- [x] 2.2 Regenerate the lock and prove the existing unit suite on Python 3.11
- [x] 2.3 Build the wheel and verify `Requires-Python` rejects 3.10 while an isolated Python 3.11 CLI succeeds

## 3. Repository-local agent skills

- [x] 3.1 Initialize `/skills/zush-setup`, `/skills/zush-configure`, and `/skills/zush-use` with generated agent metadata
- [x] 3.2 Author concise setup, configuration, and invocation workflows against the accepted public Zush contract
- [x] 3.3 Validate every skill with the skill-creator validator

## 4. Complete verification and finalization

- [x] 4.1 Run lock, Python 3.11, Ruff lint/format, unit tests, and every capability-owned Behave root independently
- [x] 4.2 Build clean source and wheel artifacts and run the isolated Python 3.11 CLI
- [x] 4.3 Reconcile the runtime capability into canonical specs and inspect retained OpenLease cohorts
- [x] 4.4 Archive the completed OpenSpec change after all gates are green
- [x] 4.5 Create only the separately authorized logical commit

## 5. ZPP stage outcomes

- [x] 5.1 `clarify` — completed: Python 3.11, dependency, skill-location, and verification boundaries are owner-confirmed and strict-valid
- [x] 5.2 `shape` — completed: one independent feature root traces both runtime-compatibility delta scenarios and proves relevant RED
- [x] 5.3 `plan-utilities` — skipped: not applicable because the accepted change only alters package/tool metadata and skill artifacts
- [x] 5.4 `mature-utilities` — skipped: not applicable because no utility boundary or executable utility behavior changes
- [x] 5.5 `wire` — completed: project metadata and package-boundary verification are green on Python 3.11
- [x] 5.6 `form-specs` — completed: the verified runtime boundary is canonical and no retained OpenLease cohorts exist
- [x] 5.7 `finalize` — completed: skills, Python 3.11 compatibility, all verification gates, canonical specs, archive, and authorized commit are coherent
