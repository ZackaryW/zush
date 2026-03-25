from __future__ import annotations

from click.testing import CliRunner

from zush import create_zush_group
from zush.config import Config
from zush.paths import DirectoryStorage


def _write_service_plugin(env_root, body: str) -> None:
    pkg = env_root / "zush_services"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(body, encoding="utf-8")


def test_create_zush_group_registers_plugin_services(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    _write_service_plugin(
        env_root,
        """
import sys
from zush.plugin import Plugin

p = Plugin()
p.service("sleeper", [sys.executable, "-c", "import time; time.sleep(60)"])
ZushPlugin = p
""",
    )

    storage = DirectoryStorage(tmp_path / "data")
    create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)

    from zush.services import read_service_registry

    registry = read_service_registry(storage)
    assert "sleeper" in registry["services"]
    assert registry["services"]["sleeper"]["command"][0]


def test_self_services_can_start_status_and_stop_service(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    _write_service_plugin(
        env_root,
        """
import sys
from zush.plugin import Plugin

p = Plugin()
p.service("sleeper", [sys.executable, "-c", "import time; time.sleep(60)"])
ZushPlugin = p
""",
    )

    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    started = runner.invoke(group, ["self", "services", "sleeper", "--start"])
    assert started.exit_code == 0
    assert "started" in started.output.lower() or "running" in started.output.lower()

    status = runner.invoke(group, ["self", "services", "sleeper", "--status"])
    assert status.exit_code == 0
    assert "running" in status.output.lower() or "healthy" in status.output.lower()

    stopped = runner.invoke(group, ["self", "services", "sleeper", "--stop"])
    assert stopped.exit_code == 0
    assert "stopped" in stopped.output.lower()


def test_self_services_auto_restart_unhealthy_service(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    _write_service_plugin(
        env_root,
        """
import sys
from zush.plugin import Plugin

def unhealthy(_state):
    return False, "unhealthy"

p = Plugin()
p.service(
    "healer",
    [sys.executable, "-c", "import time; time.sleep(60)"],
    auto_restart=True,
    healthcheck=unhealthy,
)
ZushPlugin = p
""",
    )

    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    started = runner.invoke(group, ["self", "services", "healer", "--start"])
    assert started.exit_code == 0

    status = runner.invoke(group, ["self", "services", "healer", "--status"])
    assert status.exit_code == 0
    assert "restarted" in status.output.lower()

    runner.invoke(group, ["self", "services", "healer", "--stop"])


def test_self_services_can_use_custom_control_interface(tmp_path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    _write_service_plugin(
        env_root,
        f'''
from zush.plugin import Plugin


class Control:
    def _record(self, action: str, runtime) -> None:
        runtime.state.setdefault("calls", []).append(action)
        runtime.state["control_state"] = action
        runtime.save()

    def start(self, runtime):
        self._record("start", runtime)
        return "started managed"

    def stop(self, runtime):
        self._record("stop", runtime)
        return "stopped managed"

    def restart(self, runtime):
        self._record("restart", runtime)
        return "restarted managed"

    def status(self, runtime):
        self._record("status", runtime)
        if runtime.state.get("control_state") in {{"start", "restart", "status"}}:
            return "healthy"
        return "stopped"


p = Plugin()
p.service("managed", ["ignored"], control=Control())
ZushPlugin = p
''',
    )

    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    started = runner.invoke(group, ["self", "services", "managed", "--start"])
    assert started.exit_code == 0, (started.output, repr(started.exception))
    assert "started managed" in started.output.lower()

    status = runner.invoke(group, ["self", "services", "managed", "--status"])
    assert status.exit_code == 0, (status.output, repr(status.exception))
    assert "healthy" in status.output.lower()

    restarted = runner.invoke(group, ["self", "services", "managed", "--restart"])
    assert restarted.exit_code == 0, (restarted.output, repr(restarted.exception))
    assert "restarted managed" in restarted.output.lower()

    stopped = runner.invoke(group, ["self", "services", "managed", "--stop"])
    assert stopped.exit_code == 0, (stopped.output, repr(stopped.exception))
    assert "stopped managed" in stopped.output.lower()

    from zush.services import read_service_registry

    registry = read_service_registry(storage)
    assert registry["services"]["managed"]["calls"] == ["start", "status", "restart", "stop"]