from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import zipfile
from contextlib import redirect_stderr
from email.parser import Parser
from pathlib import Path

from zush.application import Application
from zush.cli import run_cli
from zush.errors import IntegrationError
from zush.github import Repository
from zush.utils.paths import ZushPaths


class FakeGitHub:
    def __init__(self, data: dict[str, list[Repository]], login: str = "alice") -> None:
        self.data = data
        self.login = login

    def current_login(self) -> str:
        if not self.login:
            raise IntegrationError("GitHub authentication is required")
        return self.login

    def repositories(self, owner: str) -> list[Repository]:
        try:
            return self.data[owner]
        except KeyError as error:
            raise IntegrationError(f"cannot enumerate {owner}") from error


class FakeWorkspace:
    def __init__(self, paths: dict[str, Path]) -> None:
        self.paths = paths
        self.ensure_calls: list[str] = []
        self.register_calls: list[Path] = []
        self.updated: set[str] | None = None
        self.failure: str | None = None

    def ensure(self, repository: Repository) -> Path:
        target = repository.target
        self.ensure_calls.append(target)
        if self.failure == target:
            raise IntegrationError(f"failed to install {target}")
        return self.paths[target]

    def installed(self) -> dict[str, Path]:
        return self.paths

    def update_all(self, repositories: list[Repository]) -> None:
        self.updated = {item.target for item in repositories}


def verify_namespace_discovery(root: Path) -> None:
    paths, data, workspace = _fixture(root)
    ran: list[str] = []
    app = Application(paths, FakeGitHub(data), workspace, run_process=lambda argv, _env: ran.append(argv[-1]) or 0)
    assert run_cli(["~tools:hello"], app) == 0
    assert workspace.ensure_calls[-1] == "alice/tools"

    assert run_cli(["namespace", "add", "Pathverse"], app) == 0
    future = root / "future"
    future.mkdir()
    (future / "hello.py").write_text("", encoding="utf-8")
    data["Pathverse"].append(Repository("Pathverse", "future-tools", "future", ""))
    workspace.paths["Pathverse/future-tools"] = future
    assert run_cli(["Pathverse/future-tools:hello"], app) == 0

    error = io.StringIO()
    with redirect_stderr(error):
        assert run_cli(["namespace", "add", "private-org"], app) == 1
    assert "cannot enumerate" in error.getvalue()

    assert run_cli(["namespace", "remove", "Pathverse"], app) == 0
    with redirect_stderr(io.StringIO()):
        assert run_cli(["Pathverse/future-tools:hello"], app) == 2
    assert future.exists()

    config = workspace.paths["alice/.zush"] / "map.toml"
    config.write_text('[namespaces.alice]\nexclude = ["tools"]\n', encoding="utf-8")
    with redirect_stderr(io.StringIO()):
        assert run_cli(["~tools:hello"], app) == 2
    assert workspace.ensure_calls[-1] == "alice/.zush"

    unauthenticated = Application(paths, FakeGitHub(data, login=""), workspace)
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["~tools:hello"], unauthenticated) == 1
    assert "authentication" in error.getvalue()


def verify_repository_materialization(root: Path) -> None:
    paths, data, workspace = _fixture(root)
    calls: list[list[str]] = []
    app = Application(paths, FakeGitHub(data), workspace, run_process=lambda argv, _env: calls.append(argv) or 0)
    assert run_cli(["~tools:hello"], app) == 0
    assert workspace.ensure_calls[-1] == "alice/tools"
    assert workspace.updated is None

    assert run_cli(["~tools:hello"], app) == 0
    assert run_cli(["update"], app) == 0
    assert workspace.updated == {"alice/.zush", "alice/tools"}

    workspace.failure = "alice/tools"
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["~tools:hello"], app) == 1
    assert "failed to install" in error.getvalue()
    assert len(calls) == 2


def verify_script_execution(root: Path) -> None:
    paths, data, workspace = _fixture(root)
    dotted = root / "dotted"
    (dotted / "release").mkdir(parents=True)
    (dotted / "release" / "publish.py").write_text("", encoding="utf-8")
    data["Pathverse"] = [Repository("Pathverse", "scripts.tools", "dot", "")]
    workspace.paths["Pathverse/scripts.tools"] = dotted
    selected: list[tuple[list[str], int]] = []

    def run_process(argv: list[str], _environment: dict[str, str]) -> int:
        status = 7 if argv[-2:] == ["--flag", "second"] else 0
        selected.append((argv, status))
        return status

    app = Application(paths, FakeGitHub(data), workspace, run_process=run_process)
    assert run_cli(["namespace", "add", "Pathverse"], app) == 0
    assert run_cli(["Pathverse/scripts.tools:release.publish"], app) == 0
    assert selected[-1][0][0] == sys.executable
    assert selected[-1][0][1].endswith("publish.py")

    before = len(workspace.ensure_calls)
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["~tools.hello"], app) == 2
    assert "addresses use" in error.getvalue()
    assert len(workspace.ensure_calls) == before

    tools = workspace.paths["alice/tools"]
    (tools / "ambiguous.py").write_text("", encoding="utf-8")
    (tools / "ambiguous.sh").write_text("", encoding="utf-8")
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["~tools:ambiguous"], app) == 2
    assert "ambiguous" in error.getvalue()
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["~tools:missing"], app) == 2
    assert "unknown script" in error.getvalue()

    assert run_cli(["~tools:hello", "--arg", "first", "--", "--flag", "second"], app) == 7
    assert selected[-1][0][-3:] == ["first", "--flag", "second"]


def verify_structured_input(root: Path) -> None:
    paths, data, workspace = _fixture(root)
    observed: list[tuple[dict[str, object], Path]] = []

    def run_process(_argv: list[str], environment: dict[str, str]) -> int:
        path = Path(environment["ZUSH_INPUT_FILE"])
        observed.append((json.loads(path.read_text(encoding="utf-8")), path))
        return 0

    config = workspace.paths["alice/.zush"] / "map.toml"
    config.write_text(
        '[commands.typed]\ntarget = { owner = "~", repo = "tools", path = "hello" }\n'
        'default_map = { region = "default", nested = { old = 1 } }\n',
        encoding="utf-8",
    )
    app = Application(paths, FakeGitHub(data), workspace, run_process=run_process)
    assert (
        run_cli(
            [
                "run",
                "typed",
                "--map",
                '{"nested":{"new":2}}',
                "--var",
                "region=west",
                "--casted",
                "float+level=1.5",
                "--casted",
                "bool+enabled=false",
            ],
            app,
        )
        == 0
    )
    payload, input_path = observed[-1]
    assert payload == {"nested": {"new": 2}, "region": "west", "level": 1.5, "enabled": False}
    assert not input_path.exists()

    started = len(observed)
    with redirect_stderr(io.StringIO()):
        assert run_cli(["~tools:hello", "--casted", "int+value=no"], app) == 2
        assert run_cli(["~tools:hello", "--map", "[]"], app) == 2
    assert len(observed) == started


def verify_command_aliases(root: Path) -> None:
    paths, data, workspace = _fixture(root)
    config = workspace.paths["alice/.zush"] / "map.toml"
    config.write_text(
        '[commands.hello]\ntarget = { owner = "~", repo = "tools", path = "hello" }\n'
        'default_args = ["base"]\ndefault_map = { count = 2, enabled = true }\n',
        encoding="utf-8",
    )
    observed: list[tuple[list[str], dict[str, object]]] = []

    def run_process(argv: list[str], environment: dict[str, str]) -> int:
        payload = (
            json.loads(Path(environment["ZUSH_INPUT_FILE"]).read_text(encoding="utf-8"))
            if "ZUSH_INPUT_FILE" in environment
            else {}
        )
        observed.append((argv, payload))
        return 0

    app = Application(paths, FakeGitHub(data), workspace, run_process=run_process)
    assert run_cli(["run", "hello", "--arg", "extra", "--", "--flag", "--var", "not-parsed"], app) == 0
    assert observed[-1][0][-5:] == ["base", "extra", "--flag", "--var", "not-parsed"]
    assert observed[-1][1] == {"count": 2, "enabled": True}

    assert run_cli(["alias", "bind", "hello", "~tools:hello"], app) == 0
    assert run_cli(["run", "hello"], app) == 0
    assert run_cli(["alias", "unbind", "hello"], app) == 0
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["run", "hello"], app) == 2
    assert "unknown alias" in error.getvalue()

    config.write_text("not = [valid", encoding="utf-8")
    with redirect_stderr(error := io.StringIO()):
        assert run_cli(["run", "missing"], app) == 2
    assert "invalid remote configuration" in error.getvalue()

    data_without_remote = {"alice": [Repository("alice", "tools", "abc", "")], "Pathverse": []}
    app_without_remote = Application(paths, FakeGitHub(data_without_remote), workspace)
    with redirect_stderr(io.StringIO()):
        assert run_cli(["run", "missing"], app_without_remote) == 2


def verify_runtime_compatibility(root: Path) -> None:
    project = Path(__file__).parents[2]
    output = root / "dist"
    uv = shutil.which("uv")
    assert uv is not None
    build = subprocess.run(  # noqa: S603 - fixed build command
        [uv, "build", "--out-dir", str(output)],
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr or build.stdout
    wheel = next(output.glob("zush-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        metadata_path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_path).decode("utf-8"))
    assert metadata["Requires-Python"] == ">=3.12"
    assert any("saucepan-sdk" in value for value in metadata.get_all("Requires-Dist"))
    with zipfile.ZipFile(wheel) as archive:
        assert not any("/vendor/" in name for name in archive.namelist())

    run = subprocess.run(  # noqa: S603 - fixed isolated public CLI command
        [
            uv,
            "run",
            "--isolated",
            "--no-project",
            "--python",
            "3.12",
            "--with",
            str(wheel),
            "zush",
            "--version",
        ],
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr or run.stdout
    assert run.stdout.strip() == "zush 0.1.0"


def _fixture(root: Path) -> tuple[ZushPaths, dict[str, list[Repository]], FakeWorkspace]:
    paths = ZushPaths.from_environment({"ZUSH_HOME": str(root / "state")})
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "hello.py").write_text("", encoding="utf-8")
    remote = root / ".zush"
    remote.mkdir(exist_ok=True)
    data = {
        "alice": [Repository("alice", "tools", "abc", ""), Repository("alice", ".zush", "config", "")],
        "Pathverse": [],
    }
    return paths, data, FakeWorkspace({"alice/tools": tools, "alice/.zush": remote})


VERIFIERS = {
    "namespace-discovery": verify_namespace_discovery,
    "repository-materialization": verify_repository_materialization,
    "script-execution": verify_script_execution,
    "structured-input": verify_structured_input,
    "command-aliases": verify_command_aliases,
    "runtime-compatibility": verify_runtime_compatibility,
}
