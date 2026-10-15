from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_application import FakeGitHub, FakeWorkspace

from zush.application import Application
from zush.cli import run_cli
from zush.errors import ZushError
from zush.github import Repository
from zush.utils.commands import command_script, load_repository_commands
from zush.utils.paths import ZushPaths


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.paths = ZushPaths.from_environment({"ZUSH_HOME": str(self.root / "state")})
        self.data = {"alice": [Repository("alice", name, "a" * 40, "") for name in ("zeta", "alpha", "uninstalled")]}
        self.outputs = {}
        for name in ("zeta", "alpha"):
            output = self.root / name
            self.make_map(output)
            self.outputs[f"alice/{name}"] = output
        self.workspace = FakeWorkspace(self.outputs)
        self.calls = []

        def run(argv, env):
            payload = json.loads(Path(env["ZUSH_INPUT_FILE"]).read_text()) if "ZUSH_INPUT_FILE" in env else {}
            self.calls.append((argv, payload))
            return 7

        self.app = Application(self.paths, FakeGitHub(self.data), self.workspace, run_process=run)

    @staticmethod
    def make_map(output):
        folder = output / ".zush/scripts"
        folder.mkdir(parents=True)
        (folder / "deploy.py").write_text("", encoding="utf-8")
        (output / ".zush/map.toml").write_text(
            '[commands.deploy]\npath = "scripts.deploy"\ndefault_args = ["base"]\n'
            'default_map = { region = "east", retries = 2 }\n',
            encoding="utf-8",
        )

    def test_listing_is_installed_only_with_provenance(self):
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(run_cli(["commands"], self.app), 0)
        lines = output.getvalue().splitlines()
        self.assertIn("alice/alpha:deploy", lines[0])
        self.assertIn("map.toml", lines[0])
        self.assertIn("alice/zeta:deploy", lines[1])
        self.assertEqual(self.workspace.ensure_calls, [])

    def test_default_first_and_no_first_collision(self):
        self.assertEqual(run_cli(["run", "deploy"], self.app), 7)
        self.assertIn(str(self.root / "alpha"), self.calls[0][0][1])
        with redirect_stderr(error := io.StringIO()):
            self.assertEqual(run_cli(["run", "deploy", "--no-first"], self.app), 2)
        self.assertIn("alice/alpha:deploy", error.getvalue())
        self.assertIn("alice/zeta:deploy", error.getvalue())
        self.assertEqual(len(self.calls), 1)

    def test_qualified_selection_with_structured_defaults_and_raw_arguments(self):
        self.assertEqual(
            run_cli(
                [
                    "run",
                    "~zeta:deploy",
                    "--no-first",
                    "--arg",
                    "user",
                    "--var",
                    "region=west",
                    "--",
                    "--no-first",
                ],
                self.app,
            ),
            7,
        )
        argv, payload = self.calls[-1]
        self.assertIn(str(self.root / "zeta"), argv[1])
        self.assertEqual(argv[-3:], ["base", "user", "--no-first"])
        self.assertEqual(payload, {"region": "west", "retries": 2})
        self.assertEqual(self.workspace.ensure_calls, ["alice/zeta"])

    def test_global_priority_tombstone_and_qualified_bypass(self):
        # Direct addresses cannot express .zush as an empty dot segment. Bind a normal repository script.
        (self.root / "zeta" / "hello.py").write_text("", encoding="utf-8")
        self.app.bind_alias("deploy", "~zeta:hello")
        self.assertEqual(run_cli(["run", "deploy"], self.app), 7)
        self.assertTrue(self.calls[-1][0][1].endswith("hello.py"))
        self.app.unbind_alias("deploy")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(run_cli(["run", "deploy"], self.app), 2)
        self.assertEqual(run_cli(["run", "alice/alpha:deploy"], self.app), 7)

    def test_local_override_and_central_alias_are_one_effective_candidate(self):
        central = self.root / "central"
        central.mkdir()
        (central / "map.toml").write_text(
            '[commands.ship]\ntarget={owner="~",repo="alpha",path="hello"}\n',
            encoding="utf-8",
        )
        self.data["alice"].append(Repository("alice", ".zush", "c" * 40, ""))
        self.outputs["alice/.zush"] = central
        (self.root / "zeta/hello.py").write_text("", encoding="utf-8")
        self.app.bind_alias("ship", "~zeta:hello")
        self.assertEqual(run_cli(["run", "ship", "--no-first"], self.app), 7)
        self.assertIn(str(self.root / "zeta"), self.calls[-1][0][1])

    def test_qualified_request_can_acquire_one_uninstalled_repository(self):
        new = self.root / "new"
        self.make_map(new)
        original = self.workspace.ensure

        def ensure(repository):
            if repository.name == "uninstalled":
                self.outputs[repository.target] = new
            return original(repository)

        self.workspace.ensure = ensure
        self.assertEqual(run_cli(["run", "~uninstalled:deploy"], self.app), 7)
        self.assertEqual(self.workspace.ensure_calls, ["alice/uninstalled"])

    def test_only_enrolled_visible_nonexcluded_repositories_contribute(self):
        self.outputs["bob/tools"] = self.outputs["alice/alpha"]
        self.data["bob"] = [Repository("bob", "tools", "b" * 40, "")]
        self.assertNotIn("bob/tools:deploy", [item.qualified for item in self.app.commands()])
        self.app.add_namespace("bob")
        self.assertIn("bob/tools:deploy", [item.qualified for item in self.app.commands()])
        self.app.remove_namespace("bob")
        self.assertNotIn("bob/tools:deploy", [item.qualified for item in self.app.commands()])
        remote = self.root / "central"
        remote.mkdir()
        (remote / "map.toml").write_text('[namespaces.alice]\nexclude=["alpha"]\n', encoding="utf-8")
        self.data["alice"].append(Repository("alice", ".zush", "c" * 40, ""))
        self.outputs["alice/.zush"] = remote
        self.assertNotIn("alice/alpha:deploy", [item.qualified for item in self.app.commands()])
        with redirect_stderr(io.StringIO()):
            self.assertEqual(run_cli(["run", "alice/alpha:deploy"], self.app), 2)

    def test_malformed_missing_and_cross_repository_maps(self):
        self.assertEqual(load_repository_commands("alice/missing", self.root / "missing"), [])
        path = self.root / "alpha/.zush/map.toml"
        for text in ("not = [valid", '[commands.x]\ntarget={owner="bob"}', '[commands.x]\npath="../escape"'):
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ZushError, "alice/alpha.*map.toml"):
                load_repository_commands("alice/alpha", self.root / "alpha")

    def test_bind_rejects_names_reserved_for_qualified_commands(self):
        for name in ("owner/repo:deploy", "name:deploy", "owner/repo", "owner\\repo"):
            with self.assertRaisesRegex(ZushError, "unqualified token"):
                self.app.bind_alias(name, "~alpha:hello")

    def test_ambiguous_script_and_symlink_escape_rejected(self):
        command = load_repository_commands("alice/alpha", self.root / "alpha")[0]
        (self.root / "alpha/.zush/scripts/deploy.sh").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ZushError, "ambiguous"):
            command_script(command)
        # Exercise resolved containment without relying on Windows symlink privileges.
        (self.root / "alpha/.zush/scripts/deploy.sh").unlink()
        original_resolve = Path.resolve
        script = self.root / "alpha/.zush/scripts/deploy.py"

        def resolve(path, *args, **kwargs):
            return self.root / "escape.py" if path == script else original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve), self.assertRaisesRegex(ZushError, "escapes"):
            command_script(command)
