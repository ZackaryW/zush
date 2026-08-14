from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from zush.errors import ZushError
from zush.github import GitHubClient, Repository
from zush.utils.inventory import build_bucket, write_bucket
from zush.utils.state import load_namespaces, save_namespaces


class StateTests(unittest.TestCase):
    def test_namespace_round_trip_is_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "namespaces.json"
            save_namespaces(path, {"zeta", "alpha"})
            self.assertEqual(load_namespaces(path), {"alpha", "zeta"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"namespaces": ["alpha", "zeta"]})

    def test_missing_namespace_state_is_empty(self) -> None:
        self.assertEqual(load_namespaces(Path("missing-namespaces.json")), set())


class GitHubTests(unittest.TestCase):
    def test_login_and_repository_shape(self) -> None:
        outputs = {
            ("gh", "api", "user"): '{"login":"alice"}',
            (
                "gh",
                "repo",
                "list",
                "alice",
                "--limit",
                "1000",
                "--json",
                "name,nameWithOwner,description,defaultBranchRef",
            ): '[{"name":"tools","nameWithOwner":"alice/tools","description":null,"defaultBranchRef":{"oid":"abc"}}]',
        }
        client = GitHubClient(run=lambda argv: outputs[tuple(argv)])
        self.assertEqual(client.current_login(), "alice")
        self.assertEqual(client.repositories("alice"), [Repository("alice", "tools", "abc", "")])

    def test_invalid_json_shape_is_rejected(self) -> None:
        client = GitHubClient(run=lambda _argv: "[]")
        with self.assertRaises(ZushError):
            client.current_login()


class InventoryTests(unittest.TestCase):
    def test_bucket_is_deterministic_and_contains_no_commands(self) -> None:
        entries = build_bucket(
            [
                Repository("zeta", "two", "222", "Two"),
                Repository("alpha", "one", "111", "One"),
            ]
        )
        self.assertEqual([entry["url"] for entry in entries], ["alpha/one", "zeta/two"])
        self.assertEqual(entries[0]["ref"], "111")
        self.assertEqual(entries[0]["manifest"]["version"], "111")
        self.assertNotIn("commands", json.dumps(entries))

    def test_bucket_write_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bucket.json"
            write_bucket(path, [Repository("alice", "tools", "abc", "")])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))[0]["url"], "alice/tools")

    def test_empty_commit_is_rejected(self) -> None:
        with self.assertRaises(ZushError):
            build_bucket([Repository("alice", "empty", "", "")])
