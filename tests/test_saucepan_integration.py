"""Opt-in local Git test: ZUSH_TEST_SAUCEPAN=/absolute/path/to/saucepan."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from saucepan_sdk import Client
from test_application import FakeGitHub

from zush.application import Application
from zush.cli import run_cli
from zush.errors import IntegrationError
from zush.github import Repository
from zush.saucepan import SaucepanWorkspace, _external_client
from zush.utils.paths import ZushPaths


@unittest.skipUnless(os.environ.get("ZUSH_TEST_SAUCEPAN"), "set ZUSH_TEST_SAUCEPAN to test an isolated real manager")
class RealManagerTests(unittest.TestCase):
    def test_external_manager_profile_preview_does_not_initialize_a_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "uninitialized"
            with patch.dict(os.environ, {
                "ZUSH_SAUCEPAN": os.environ["ZUSH_TEST_SAUCEPAN"],
                "ZUSH_SAUCEPAN_ROOT": str(root),
            }):
                client = _external_client()
                profile = client.profile("explicit-update")
            self.assertFalse(profile["for_install"])
            self.assertTrue(profile["combined_policy_refs"])
            self.assertFalse(root.exists())

    def test_central_alias_local_commands_and_updates_use_real_retained_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            origins = {name: base / name for name in ("tools", "central")}

            def git(repo, *args):
                return subprocess.run(  # noqa: S603 - fixed local fixture commands
                    ["git", "-C", str(repo), *args],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()

            for repo in origins.values():
                repo.mkdir()
                git(repo, "init")
                git(repo, "config", "user.name", "Zush fixture")
                git(repo, "config", "user.email", "fixture@example.invalid")
            tools = origins["tools"]
            (tools / ".zush").mkdir()
            (tools / ".zush/map.toml").write_text('[commands.deploy]\npath="deploy"\n', encoding="utf-8")
            (tools / ".zush/deploy.py").write_text("print('A')\n", encoding="utf-8")
            (tools / "hello.py").write_text("print('global')\n", encoding="utf-8")
            (origins["central"] / "map.toml").write_text(
                '[commands.hello]\ntarget={owner="~",repo="tools",path="hello"}\n',
                encoding="utf-8",
            )
            for repo in origins.values():
                git(repo, "add", ".")
                git(repo, "commit", "-m", "A")
            data = {
                "alice": [
                    Repository("alice", "tools", git(tools, "rev-parse", "HEAD"), ""),
                    Repository("alice", ".zush", git(origins["central"], "rev-parse", "HEAD"), ""),
                ]
            }
            manager_root = base / "manager"
            client = Client(executable=os.environ["ZUSH_TEST_SAUCEPAN"], root=str(manager_root))
            client.init()
            paths = ZushPaths.from_environment({"ZUSH_HOME": str(base / "state")})
            workspace = SaucepanWorkspace(
                paths.bindings,
                client=client,
                origin=lambda repo: str(origins["central" if repo.name == ".zush" else "tools"]),
            )
            printed = []

            def run(argv, env):
                completed = subprocess.run(argv, env=env, capture_output=True, text=True, check=False)  # noqa: S603
                printed.append(completed.stdout.strip())
                return completed.returncode

            app = Application(paths, FakeGitHub(data), workspace, run_process=run)
            self.assertEqual(run_cli(["run", "hello"], app), 0)
            self.assertEqual(printed[-1], "global")
            self.assertEqual(run_cli(["run", "~tools:deploy"], app), 0)
            self.assertEqual(printed[-1], "A")
            first = workspace.ensure(data["alice"][0])
            (tools / ".zush/deploy.py").write_text("print('B')\n", encoding="utf-8")
            git(tools, "add", ".")
            git(tools, "commit", "-m", "B")
            data["alice"][0] = Repository("alice", "tools", git(tools, "rev-parse", "HEAD"), "")
            self.assertEqual(run_cli(["run", "deploy"], app), 0)
            self.assertEqual(printed[-1], "A")
            self.assertEqual(run_cli(["update"], app), 0)
            self.assertEqual(run_cli(["run", "deploy"], app), 0)
            self.assertEqual(printed[-1], "B")
            client.reclaim()
            self.assertTrue(first.is_dir())
            data["alice"][0] = Repository("alice", "tools", "f" * 40, "")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(run_cli(["update"], app), 1)
            self.assertEqual(run_cli(["run", "deploy"], app), 0)
            self.assertEqual(printed[-1], "B")
            self.assertFalse((manager_root / "claim").exists())

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
            profile = client.profile("explicit-update")
            binding = json.loads(workspace.bindings.read_text())["selected"]["fixture/tools"]
            self.assertEqual(binding["policy_catalog"], profile["catalog"])
            self.assertEqual(binding["policy_refs"], profile["combined_policy_refs"])
            group = client.show_group(binding["group_uuid"])
            self.assertEqual(group["definition"]["members"][0]["target"]["policy_refs"], binding["policy_refs"])
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
