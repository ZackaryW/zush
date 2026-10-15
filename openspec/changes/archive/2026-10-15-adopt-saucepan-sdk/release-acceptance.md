# Saucepan 0.10 release acceptance

Verified on Windows x86_64 with CPython 3.12.13 on 2026-10-15. The distribution used the installed Zush wheel and published SDK wheel, not editable source imports.

Release: https://github.com/ZackaryW/saucepan/releases/tag/v0.10.0

- Manifest Rust tag: `v0.10.0`
- Manifest commit and pinned dependency: `8a2d04e7d2e393c035715520254bdd5955651873`
- Python SDK: `0.2.0`
- Wheel SHA256: `0d2ec50225674a07f168d88c7ea8a5692726eb3c652314222e0f18cb8ae0325e`
- Extracted Windows manager SHA256: `778c4d665802961e4dc424e3d2328576698c92b65af3053e24e19716cbc01591`
- Manager version: `saucepan 0.10.0+v0.10.0`
- Parent release verification matched the archive and SDK package against published SHA256SUMS; this consumer separately checked the wheel hash and manifest fields.

## Reproduction

```powershell
uv sync --locked
uv build
uv venv --python 3.12 target/profile-release-venv
uv pip install --python target/profile-release-venv/Scripts/python.exe --no-deps dist/zush-0.1.0-py3-none-any.whl
uv pip install --python target/profile-release-venv/Scripts/python.exe 'filelock>=3.20,<4' PATH/TO/saucepan_sdk-0.2.0-py3-none-any.whl
$env:ZUSH_TEST_SAUCEPAN = 'ABSOLUTE/PATH/TO/windows-x64/saucepan.exe'
& target/profile-release-venv/Scripts/python.exe -m unittest discover -s tests -v
```

47 tests passed, zero skipped. Integration includes the external-manager version gate and root-free profile preview, actual explicit-update catalog registration and group refs, central aliases and repository-local command execution, no implicit refresh, explicit Git commit updates, failed-update preservation, and reclaim retaining previous pinned outputs. No application registration or keyring configuration was needed. Help/version passed in the installed environment. Import paths were under `target/profile-release-venv/Lib/site-packages` for both Zush and Saucepan SDK.

Other verification: 29 behavior scenarios passed across all six capability folders; Ruff (`src tests features`), wheel/sdist build, locked SDK installation from the pinned release Git commit, and strict OpenSpec validation passed. The earlier provisional integration run used a local fixture binary reporting `0.9.0+lifecycle-b`; it is superseded by this published-release acceptance and was not counted as release verification.

No live private GitHub retrieval, macOS/Linux native runners, or keyring protection was tested. Git origins in integration tests are local fixtures and all manager stores are temporary. No changes were made to the user's real store. Active change artifacts remain excluded from implementation commits; no pushes or tags were performed.
