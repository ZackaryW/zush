from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from zush.errors import ZushError
from zush.saucepan import SaucepanWorkspace


class FakeSaucepan:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.index: list[dict] = []
        self.buckets: list[dict] = []
        self.fail_install = False

    def __call__(self, argv: list[str]) -> str:
        command = tuple(argv[2:])
        self.calls.append(command)
        if command == ("cat", "index"):
            return json.dumps(self.index)
        if command == ("cat", "buckets"):
            return json.dumps(self.buckets)
        if command[:2] == ("bucket", "add"):
            self.buckets.append({"url": command[2]})
            return ""
        if command[:1] == ("install",):
            if self.fail_install:
                raise ZushError("install failed")
            target = command[1]
            self.index.append(
                {
                    "repo": target,
                    "sauce": {"name": "custom-name", "version": "1", "description": ""},
                }
            )
            return ""
        if command[:1] == ("path",):
            return f"C:/managed/{command[1]}\n"
        if command[:1] in (("update",), ("uninstall",)):
            return ""
        raise AssertionError(command)


class SaucepanTests(unittest.TestCase):
    def test_register_index_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeSaucepan()
            workspace = SaucepanWorkspace(Path(directory), binary="saucepan", run=fake)
            bucket = Path(directory) / "bucket.json"
            workspace.register_index(bucket)
            workspace.register_index(bucket)
            additions = [call for call in fake.calls if call[:2] == ("bucket", "add")]
            self.assertEqual(additions, [("bucket", "add", str(bucket))])

    def test_ensure_uses_provenance_and_reuses_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeSaucepan()
            workspace = SaucepanWorkspace(Path(directory), binary="saucepan", run=fake)
            first = workspace.ensure("alice/tools")
            second = workspace.ensure("alice/tools")
            self.assertEqual(first, Path("C:/managed/custom-name"))
            self.assertEqual(second, first)
            self.assertEqual([call for call in fake.calls if call[:1] == ("install",)], [("install", "alice/tools")])

    def test_update_and_uninstall_use_manifest_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeSaucepan()
            fake.index = [
                {"repo": "alice/tools", "sauce": {"name": "tools-cli", "version": "1", "description": ""}},
                {"repo": "other/repo", "sauce": {"name": "other", "version": "1", "description": ""}},
            ]
            workspace = SaucepanWorkspace(Path(directory), binary="saucepan", run=fake)
            workspace.update_all({"alice/tools"})
            workspace.uninstall("alice/tools")
            self.assertIn(("update", "tools-cli"), fake.calls)
            self.assertIn(("uninstall", "tools-cli"), fake.calls)
            self.assertNotIn(("update", "other"), fake.calls)

    def test_install_failure_does_not_return_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeSaucepan()
            fake.fail_install = True
            workspace = SaucepanWorkspace(Path(directory), binary="saucepan", run=fake)
            with self.assertRaises(ZushError):
                workspace.ensure("alice/tools")
