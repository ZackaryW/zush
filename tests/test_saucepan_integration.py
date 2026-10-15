"""Opt-in local Git test: ZUSH_TEST_SAUCEPAN=/absolute/path/to/saucepan."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from saucepan_sdk import Client

from zush.errors import IntegrationError
from zush.github import Repository
from zush.saucepan import SaucepanWorkspace


@unittest.skipUnless(os.environ.get("ZUSH_TEST_SAUCEPAN"), "set ZUSH_TEST_SAUCEPAN to test an isolated real manager")
class RealManagerTests(unittest.TestCase):
    def test_local_git_retained_generations(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "origin"
            repo.mkdir()

            def git(*args):
                return subprocess.run(  # noqa: S603,S607 - fixed local fixture commands
                    ["git", "-C", str(repo), *args],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=True,  # noqa: S607
                ).stdout.strip()

            git("init")
            git("config", "user.name", "Zush fixture")
            git("config", "user.email", "fixture@example.invalid")
            (repo / "hello.py").write_text("print('A')\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "A")
            first_commit = git("rev-parse", "HEAD")
            client = Client(executable=os.environ["ZUSH_TEST_SAUCEPAN"], root=str(base / "manager"))
            client.init()
            workspace = SaucepanWorkspace(base / "state/bindings.json", client=client, origin=lambda _: str(repo))
            first_repo = Repository("fixture", "tools", first_commit, "")
            first = workspace.ensure(first_repo)
            self.assertEqual((first / "hello.py").read_text(), "print('A')\n")
            (repo / "hello.py").write_text("print('B')\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "B")
            second_repo = Repository("fixture", "tools", git("rev-parse", "HEAD"), "")
            self.assertEqual(workspace.ensure(second_repo), first)
            workspace.update_all([second_repo])
            second = workspace.ensure(second_repo)
            self.assertNotEqual(first, second)
            client.reclaim()
            self.assertEqual((first / "hello.py").read_text(), "print('A')\n")
            self.assertEqual((second / "hello.py").read_text(), "print('B')\n")
            with self.assertRaises(IntegrationError):
                workspace.update_all([Repository("fixture", "tools", "f" * 40, "")])
            self.assertEqual(workspace.ensure(second_repo), second)
