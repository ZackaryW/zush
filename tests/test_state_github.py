from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from zush.errors import ZushError
from zush.github import GitHubClient, Repository
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
        def run(argv):
            if argv == ["gh", "api", "user"]:
                return '{"login":"alice"}'
            self.assertEqual(argv[:3], ["gh", "api", "graphql"])
            self.assertIn("target { oid }", argv[4])
            self.assertIn("ownerAffiliations:[OWNER]", argv[4])
            return json.dumps(
                {
                    "data": {
                        "repositoryOwner": {
                            "repositories": {
                                "nodes": [
                                    {
                                        "name": "tools",
                                        "nameWithOwner": "alice/tools",
                                        "description": None,
                                        "defaultBranchRef": {"target": {"oid": "abc"}},
                                    },
                                    {"name": "empty", "defaultBranchRef": None},
                                ],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            )

        client = GitHubClient(run=run)
        self.assertEqual(client.current_login(), "alice")
        self.assertEqual(client.repositories("alice"), [Repository("alice", "tools", "abc", "")])

    def test_invalid_json_shape_is_rejected(self) -> None:
        client = GitHubClient(run=lambda _argv: "[]")
        with self.assertRaises(ZushError):
            client.current_login()

    def test_pages_are_followed_and_repeated_cursor_is_rejected(self):
        calls = []

        def run(argv):
            calls.append(argv)
            return json.dumps(
                {
                    "data": {
                        "repositoryOwner": {
                            "repositories": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": len(calls) == 1, "endCursor": "next"},
                            }
                        }
                    }
                }
            )

        self.assertEqual(GitHubClient(run=run).repositories("alice"), [])
        self.assertEqual(len(calls), 2)
        self.assertIn("cursor=next", calls[1])

        repeated = json.dumps(
            {
                "data": {
                    "repositoryOwner": {
                        "repositories": {
                            "nodes": [],
                            "pageInfo": {"hasNextPage": True, "endCursor": "same"},
                        }
                    }
                }
            }
        )
        with self.assertRaisesRegex(ZushError, "invalid GitHub repository page"):
            GitHubClient(run=lambda _: repeated).repositories("alice")
