from __future__ import annotations

from click.testing import CliRunner

from zush import create_zush_group
from zush.configparse.config import Config
from zush.core.storage import DirectoryStorage


def test_global_runtime_store_behaves_like_process_scoped_registry() -> None:
    from zush.core.runtime import g

    g.clear()
    marker = object()
    g["marker"] = marker

    assert g["marker"] is marker
    assert g.get("marker") is marker
    assert g.ensure("marker", lambda: object()) is marker
    assert g.ensure("other", lambda: "value") == "value"


def test_create_zush_group_registers_plugin_provided_globals(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_provider"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.core.runtime import g
from zush.pluginloader.plugin import Plugin

p = Plugin()
p.provide("shared_text", "hello")

@click.command("show")
def show_cmd():
    click.echo(g["shared_text"])

p.group("demo").command("show", callback=show_cmd.callback)
ZushPlugin = p
""",
        encoding="utf-8",
    )

    from zush.core.runtime import g

    g.clear()
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)

    assert g["shared_text"] == "hello"

    result = CliRunner().invoke(group, ["demo", "show"])
    assert result.exit_code == 0
    assert "hello" in result.output


def test_create_zush_group_registers_lazy_provider_factories(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_provider"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.core.runtime import g
from zush.pluginloader.plugin import Plugin

CALLS = 0


def build_text():
    global CALLS
    CALLS += 1
    return f"hello-{CALLS}"


p = Plugin()
p.provide_factory("shared_text", build_text)

@click.command("show")
def show_cmd():
    click.echo(g["shared_text"])


@click.command("count")
def count_cmd():
    click.echo(str(CALLS))


demo = p.group("demo")
demo.command("show", callback=show_cmd.callback)
demo.command("count", callback=count_cmd.callback)
ZushPlugin = p
""",
        encoding="utf-8",
    )

    from zush.core.runtime import g

    g.clear()
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    count = runner.invoke(group, ["demo", "count"])
    assert count.exit_code == 0
    assert count.output.strip() == "0"

    first = runner.invoke(group, ["demo", "show"])
    assert first.exit_code == 0
    assert first.output.strip() == "hello-1"

    second = runner.invoke(group, ["demo", "show"])
    assert second.exit_code == 0
    assert second.output.strip() == "hello-1"

    count = runner.invoke(group, ["demo", "count"])
    assert count.exit_code == 0
    assert count.output.strip() == "1"


def test_provider_factories_can_ensure_service_readiness(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_provider"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import json

import click

from zush.core.runtime import g
from zush.pluginloader.plugin import Plugin

START_CALLS = 0


class Control:
    def start(self, runtime):
        global START_CALLS
        START_CALLS += 1
        runtime.state["running"] = True
        runtime.save()
        return "started managed"

    def stop(self, runtime):
        runtime.state["running"] = False
        runtime.save()
        return "stopped managed"

    def status(self, runtime):
        return "healthy" if runtime.state.get("running") else "stopped"


def build_client(runtime):
    runtime.ensure_service("managed")
    return {"service": "managed", "starts": START_CALLS}


p = Plugin()
p.service("managed", ["ignored"], control=Control())
p.provide_factory("client", build_client)

@click.command("client")
def client_cmd():
    click.echo(json.dumps(g["client"], sort_keys=True))


@click.command("count")
def count_cmd():
    click.echo(str(START_CALLS))


demo = p.group("demo")
demo.command("client", callback=client_cmd.callback)
demo.command("count", callback=count_cmd.callback)
ZushPlugin = p
""",
        encoding="utf-8",
    )

    from zush.core.runtime import g

    g.clear()
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    count = runner.invoke(group, ["demo", "count"])
    assert count.exit_code == 0
    assert count.output.strip() == "0"

    client = runner.invoke(group, ["demo", "client"])
    assert client.exit_code == 0
    assert client.output.strip() == '{"service": "managed", "starts": 1}'


def test_provider_factories_can_rebuild_and_teardown_on_service_change(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_provider"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import json

import click

from zush.core.runtime import g
from zush.pluginloader.plugin import Plugin

START_CALLS = 0
TEARDOWNS = []


class Control:
    def start(self, runtime):
        global START_CALLS
        START_CALLS += 1
        runtime.state["running"] = True
        runtime.save()
        return f"started managed {START_CALLS}"

    def stop(self, runtime):
        runtime.state["running"] = False
        runtime.save()
        return "stopped managed"

    def restart(self, runtime):
        self.stop(runtime)
        return self.start(runtime).replace("started", "restarted", 1)

    def status(self, runtime):
        return "healthy" if runtime.state.get("running") else "stopped"


def build_client(runtime):
    return {"service": "managed", "starts": START_CALLS}


def teardown_client(value):
    TEARDOWNS.append(value["starts"])


p = Plugin()
p.service("managed", ["ignored"], control=Control())
p.provide_factory(
    "client",
    build_client,
    service="managed",
    recreate_on_restart=True,
    teardown=teardown_client,
)

@click.command("client")
def client_cmd():
    click.echo(json.dumps(g["client"], sort_keys=True))


@click.command("teardowns")
def teardown_cmd():
    click.echo(json.dumps(TEARDOWNS))


demo = p.group("demo")
demo.command("client", callback=client_cmd.callback)
demo.command("teardowns", callback=teardown_cmd.callback)
ZushPlugin = p
""",
        encoding="utf-8",
    )

    from zush.core.runtime import g

    g.clear()
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    first = runner.invoke(group, ["demo", "client"])
    assert first.exit_code == 0
    assert first.output.strip() == '{"service": "managed", "starts": 1}'

    restarted = runner.invoke(group, ["self", "services", "managed", "--restart"])
    assert restarted.exit_code == 0

    second = runner.invoke(group, ["demo", "client"])
    assert second.exit_code == 0
    assert second.output.strip() == '{"service": "managed", "starts": 2}'

    teardowns = runner.invoke(group, ["demo", "teardowns"])
    assert teardowns.exit_code == 0
    assert teardowns.output.strip() == "[1]"

    stopped = runner.invoke(group, ["self", "services", "managed", "--stop"])
    assert stopped.exit_code == 0

    teardowns = runner.invoke(group, ["demo", "teardowns"])
    assert teardowns.exit_code == 0
    assert teardowns.output.strip() == "[1, 2]"