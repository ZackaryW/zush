from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from zush.application import Application, Invocation
from zush.cli import run_cli
from zush.github import Repository
from zush.utils.paths import ZushPaths


class FakeGitHub:
    def __init__(self, repositories: dict[str, list[Repository]]) -> None:
        self.data = repositories

    def current_login(self) -> str:
        return "alice"

    def repositories(self, owner: str) -> list[Repository]:
        if owner not in self.data:
            raise RuntimeError(f"cannot enumerate {owner}")
        return self.data[owner]


class FakeWorkspace:
    def __init__(self, paths: dict[str, Path]) -> None:
        self.paths = paths
        self.ensure_calls: list[str] = []
        self.updated: set[str] | None = None
        self.registered: Path | None = None

    def ensure(self, repository: Repository) -> Path:
        target = repository.target
        self.ensure_calls.append(target)
        return self.paths[target]

    def installed(self, targets: set[str] | None = None) -> dict[str, Path]:
        return {
            key.casefold(): value for key, value in self.paths.items() if targets is None or key.casefold() in targets
        }

    def update_all(self, repositories: list[Repository]) -> None:
        self.updated = {item.target for item in repositories}


class ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.paths = ZushPaths.from_environment({"ZUSH_HOME": str(root / "state")})
        self.tools = root / "tools"
        (self.tools / "scripts").mkdir(parents=True)
        (self.tools / "scripts" / "hello.py").write_text("", encoding="utf-8")
        self.remote = root / ".zush"
        self.remote.mkdir()
        self.repositories = {
            "alice": [
                Repository("alice", "tools", "abc", ""),
                Repository("alice", ".zush", "config", ""),
            ],
            "Pathverse": [Repository("Pathverse", "shared", "def", "")],
        }
        self.workspace = FakeWorkspace({"alice/tools": self.tools, "alice/.zush": self.remote})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_direct_execution_preserves_args_payload_and_status(self) -> None:
        observed: dict[str, object] = {}

        def run_process(argv: list[str], environment: dict[str, str]) -> int:
            observed["argv"] = argv
            input_path = Path(environment["ZUSH_INPUT_FILE"])
            observed["payload"] = json.loads(input_path.read_text(encoding="utf-8"))
            observed["input_path"] = input_path
            return 7

        app = Application(self.paths, FakeGitHub(self.repositories), self.workspace, run_process=run_process)
        result = app.execute(
            "~tools:scripts.hello",
            Invocation(args=("first", "--flag"), variables=("region=west",), casted=("float+level=1.5",)),
        )
        self.assertEqual(result, 7)
        self.assertEqual(observed["argv"][-2:], ["first", "--flag"])
        self.assertEqual(observed["payload"], {"region": "west", "level": 1.5})
        self.assertFalse(observed["input_path"].exists())
        self.assertEqual(self.workspace.ensure_calls, ["alice/.zush", "alice/tools"])

    def test_remote_exclusion_blocks_target_before_ensure(self) -> None:
        (self.remote / "map.toml").write_text('[namespaces.alice]\nexclude = ["tools"]\n', encoding="utf-8")
        app = Application(self.paths, FakeGitHub(self.repositories), self.workspace)
        error = io.StringIO()
        with redirect_stderr(error):
            status = run_cli(["~tools:scripts.hello"], app)
        self.assertEqual(status, 2)
        self.assertIn("excluded", error.getvalue())
        self.assertEqual(self.workspace.ensure_calls, ["alice/.zush"])

    def test_alias_bind_run_and_unbind_use_local_overlay(self) -> None:
        observed: list[str] = []

        def run_process(argv: list[str], _environment: dict[str, str]) -> int:
            observed.extend(argv)
            return 0

        app = Application(self.paths, FakeGitHub(self.repositories), self.workspace, run_process=run_process)
        self.assertEqual(run_cli(["alias", "bind", "hello", "~tools:scripts.hello"], app), 0)
        self.assertEqual(run_cli(["run", "hello", "--arg", "base", "--", "--flag"], app), 0)
        self.assertEqual(observed[-2:], ["base", "--flag"])
        self.assertEqual(run_cli(["alias", "unbind", "hello"], app), 0)
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(run_cli(["run", "hello"], app), 2)
        self.assertIn("unknown alias", error.getvalue())

    def test_namespace_commands_and_explicit_update(self) -> None:
        app = Application(self.paths, FakeGitHub(self.repositories), self.workspace)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(run_cli(["namespace", "add", "Pathverse"], app), 0)
            self.assertEqual(run_cli(["namespace", "list"], app), 0)
        self.assertIn("Pathverse", output.getvalue())

        self.assertEqual(run_cli(["update"], app), 0)
        self.assertEqual(self.workspace.updated, {"alice/.zush", "alice/tools", "Pathverse/shared"})

        self.assertEqual(run_cli(["namespace", "remove", "Pathverse"], app), 0)
        self.assertEqual(app.list_namespaces(), ())
