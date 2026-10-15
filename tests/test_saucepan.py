from __future__ import annotations

import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from filelock import FileLock
from saucepan_sdk import SaucepanError, TransportError

from zush.errors import IntegrationError
from zush.github import Repository
from zush.saucepan import SaucepanWorkspace


class FakeClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.groups: dict = {}
        self.receipts: dict = {}
        self.entries: dict = {}
        self.calls: list = []
        self.fail = False
        self.lose_receipt = False
        self.invalid = False

    def register_policies(self, policies):
        self.calls.append(("policies", policies))

    def register_source(self, request):
        self.calls.append(("source", request))
        return {"uuid": "source", "source": request}

    def register_group(self, request):
        key = request["registration_key"]
        return self.groups.setdefault(key, {"uuid": key, "revision": 0, "definition": request})

    def prepare_group(self, uuid, *, expected_revision, pin):
        self.calls.append(("prepare", uuid, expected_revision, copy.deepcopy(pin)))
        key = pin["registration_key"]
        if self.fail:
            raise SaucepanError("source_error", "", {})
        if key not in self.receipts:
            group = copy.deepcopy(self.groups[uuid])
            target = group["definition"]["members"][0]["target"]
            commit = target["selector"]["commit"]
            output = f"output-{commit}"
            folder = self.root / output
            folder.mkdir(exist_ok=True)
            self.entries[output] = {
                "request": target,
                "state": "ready",
                "resolved": {"commit": commit},
            }
            group.update(revision=1, selected={"members": {"repository": {"output_uuid": output}}})
            self.receipts[key] = {
                "group": group,
                "stale": [],
                "resources": {"members": {"repository": {"directory": str(folder), "output_uuid": output}}},
                "pin": {"uuid": key, "state": "active", "request": {**pin, "outputs": [output]}},
            }
        if self.lose_receipt:
            self.lose_receipt = False
            raise TransportError("timeout", started=True, indeterminate=True)
        return self.receipts[key]

    def inspect(self, uuid):
        entry = copy.deepcopy(self.entries[uuid])
        if self.invalid:
            entry["request"]["source_uuid"] = "other-source"
        return entry

    def pin(self, uuid):
        receipt = self.receipts[uuid]
        output = receipt["pin"]["request"]["outputs"][0]
        return {**receipt["pin"], "outputs": {output: {"path": str(self.root / output), "available": True}}}


class SaucepanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.client = FakeClient(self.root)
        self.path = self.root / "bindings.json"
        self.workspace = SaucepanWorkspace(self.path, client=self.client)
        self.repo = Repository("alice", "tools", "a" * 40, "")

    def test_ensure_reuses_retained_commit_without_refresh(self):
        first = self.workspace.ensure(self.repo)
        second = self.workspace.ensure(Repository("alice", "tools", "b" * 40, ""))
        self.assertEqual(first, second)
        self.assertEqual(len([call for call in self.client.calls if call[0] == "prepare"]), 1)
        self.assertEqual(self.workspace.installed(), {"alice/tools": first})

    def test_updates_preserve_old_generations_and_failed_update_binding(self):
        old = self.workspace.ensure(self.repo)
        self.workspace.update_all([Repository("alice", "tools", "b" * 40, "")])
        new = self.workspace.ensure(self.repo)
        self.assertNotEqual(old, new)
        self.assertTrue(old.is_dir())
        self.client.fail = True
        with self.assertRaises(IntegrationError):
            self.workspace.update_all([Repository("alice", "tools", "c" * 40, "")])
        self.assertEqual(self.workspace.ensure(self.repo), new)
        self.assertEqual(len(json.loads(self.path.read_text())["history"]), 1)

    def test_lost_receipt_retries_original_identity_and_revision(self):
        self.client.lose_receipt = True
        with self.assertRaises(IntegrationError):
            self.workspace.ensure(self.repo)
        self.assertFalse(json.loads(self.path.read_text())["selected"])
        self.workspace.ensure(self.repo)
        calls = [call for call in self.client.calls if call[0] == "prepare"]
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(len(self.client.receipts), 1)

    def test_invalid_source_provenance_is_not_published(self):
        self.client.invalid = True
        with self.assertRaisesRegex(IntegrationError, "Invalid retained"):
            self.workspace.ensure(self.repo)
        self.assertFalse(json.loads(self.path.read_text())["selected"])

    def test_bounded_lock_and_concurrent_ensure(self):
        self.workspace.lock_timeout = 0.01
        with FileLock(str(self.path) + ".lock"), self.assertRaisesRegex(IntegrationError, "lock"):
            self.workspace.ensure(self.repo)
        self.workspace.lock_timeout = 2
        with ThreadPoolExecutor(max_workers=2) as pool:
            paths = list(pool.map(lambda _: self.workspace.ensure(self.repo), range(2)))
        self.assertEqual(paths[0], paths[1])
        self.assertEqual(len(self.client.receipts), 1)

    def test_missing_manager_is_actionable_and_construction_has_no_io(self):
        fresh = self.root / "unused" / "bindings.json"
        workspace = SaucepanWorkspace(fresh)
        self.assertFalse(fresh.parent.exists())
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
            self.assertRaisesRegex(IntegrationError, "Install Saucepan"),
        ):
            workspace.ensure(self.repo)
