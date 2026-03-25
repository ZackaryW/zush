from __future__ import annotations

import socket
import time
from pathlib import Path

import httpx
from click.testing import CliRunner

from zush import create_zush_group
from zush.config import Config
from zush.paths import DirectoryStorage


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_flask_service_plugin(env_root: Path, port: int) -> None:
    pkg = env_root / "zush_flask_tx"
    pkg.mkdir()
    (pkg / "app.py").write_text(
        f"""
from flask import Flask, jsonify

app = Flask(__name__)
STATE = {{"pending": [], "committed": []}}


@app.get("/health")
def health():
    return jsonify({{"ok": True}})


@app.post("/tx/begin")
def begin():
    STATE["pending"] = []
    return jsonify(STATE)


@app.post("/tx/stage/<value>")
def stage(value: str):
    STATE["pending"].append(value)
    return jsonify(STATE)


@app.post("/tx/commit")
def commit():
    STATE["committed"].extend(STATE["pending"])
    STATE["pending"] = []
    return jsonify(STATE)


@app.post("/tx/rollback")
def rollback():
    STATE["pending"] = []
    return jsonify(STATE)


@app.get("/tx/state")
def state():
    return jsonify(STATE)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port={port}, debug=False, use_reloader=False)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (pkg / "__zush__.py").write_text(
        f"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import httpx

from zush.plugin import Plugin
from zush.runtime import g


PORT = {port}
BASE_URL = f"http://127.0.0.1:{{PORT}}"


def _client() -> httpx.Client:
    return g.ensure("tx_client", lambda: httpx.Client(base_url=BASE_URL, timeout=2.0))


def _health(_state):
    try:
        response = httpx.get(f"{{BASE_URL}}/health", timeout=0.5)
        if response.status_code == 200 and response.json().get("ok"):
            return True, "healthy"
        return False, f"status={{response.status_code}}"
    except Exception as exc:
        return False, str(exc)


def url_cmd() -> None:
    click.echo(g["service_url"])


def begin_cmd() -> None:
    _client().post("/tx/begin").raise_for_status()
    click.echo("begun")


def stage_cmd(value: str) -> None:
    _client().post(f"/tx/stage/{{value}}").raise_for_status()
    click.echo(f"staged {{value}}")


def commit_cmd() -> None:
    _client().post("/tx/commit").raise_for_status()
    click.echo("committed")


def rollback_cmd() -> None:
    _client().post("/tx/rollback").raise_for_status()
    click.echo("rolled back")


def state_cmd() -> None:
    response = _client().get("/tx/state")
    response.raise_for_status()
    click.echo(json.dumps(response.json(), sort_keys=True))


p = Plugin()
p.provide("service_url", BASE_URL)
p.service(
    "flask-tx",
    [sys.executable, str(Path(__file__).with_name("app.py"))],
    auto_restart=True,
    healthcheck=_health,
)
tx = p.group("tx")
tx.command("url", callback=url_cmd)
tx.command("begin", callback=begin_cmd)
tx.command("stage", callback=stage_cmd, params=[click.Argument(["value"])])
tx.command("commit", callback=commit_cmd)
tx.command("rollback", callback=rollback_cmd)
tx.command("state", callback=state_cmd)
ZushPlugin = p
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_unhealthy_flask_service_plugin(env_root: Path, port: int) -> None:
    pkg = env_root / "zush_flask_health"
    pkg.mkdir()
    (pkg / "app.py").write_text(
        f"""
from flask import Flask, jsonify

app = Flask(__name__)
STATE = {{"healthy": True}}


@app.get("/health")
def health():
    return jsonify({{"ok": STATE["healthy"]}}), (200 if STATE["healthy"] else 503)


@app.post("/health/fail")
def fail_health():
    STATE["healthy"] = False
    return jsonify(STATE)


@app.get("/health/state")
def health_state():
    return jsonify(STATE)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port={port}, debug=False, use_reloader=False)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (pkg / "__zush__.py").write_text(
        f"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import httpx

from zush.plugin import Plugin
from zush.runtime import g


PORT = {port}
BASE_URL = f"http://127.0.0.1:{{PORT}}"


def _health(_state):
    try:
        response = httpx.get(f"{{BASE_URL}}/health", timeout=0.5)
        if response.status_code == 200 and response.json().get("ok"):
            return True, "healthy"
        return False, f"status={{response.status_code}}"
    except Exception as exc:
        return False, str(exc)


def url_cmd() -> None:
    click.echo(g["health_url"])


p = Plugin()
p.provide("health_url", BASE_URL)
p.service(
    "flask-health",
    [sys.executable, str(Path(__file__).with_name("app.py"))],
    auto_restart=True,
    healthcheck=_health,
)
p.group("healthsvc").command("url", callback=url_cmd)
ZushPlugin = p
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _wait_for_service(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.5)
            if response.status_code == 200 and response.json().get("ok"):
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError("Flask service did not become healthy in time")


def test_flask_service_full_integration_cycle(tmp_path: Path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    port = _reserve_port()
    base_url = f"http://127.0.0.1:{port}"
    _write_flask_service_plugin(env_root, port)

    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    started = runner.invoke(group, ["self", "services", "flask-tx", "--start"])
    assert started.exit_code == 0

    try:
        _wait_for_service(base_url)

        status = runner.invoke(group, ["self", "services", "flask-tx", "--status"])
        assert status.exit_code == 0
        assert "healthy" in status.output.lower()

        service_url = runner.invoke(group, ["tx", "url"])
        assert service_url.exit_code == 0
        assert base_url in service_url.output

        assert runner.invoke(group, ["tx", "begin"]).exit_code == 0
        assert runner.invoke(group, ["tx", "stage", "alpha"]).exit_code == 0
        state = runner.invoke(group, ["tx", "state"])
        assert state.exit_code == 0
        assert '"pending": ["alpha"]' in state.output
        assert runner.invoke(group, ["tx", "rollback"]).exit_code == 0
        state = runner.invoke(group, ["tx", "state"])
        assert '"pending": []' in state.output

        assert runner.invoke(group, ["tx", "begin"]).exit_code == 0
        assert runner.invoke(group, ["tx", "stage", "beta"]).exit_code == 0
        assert runner.invoke(group, ["tx", "commit"]).exit_code == 0
        state = runner.invoke(group, ["tx", "state"])
        assert '"committed": ["beta"]' in state.output

        restarted = runner.invoke(group, ["self", "services", "flask-tx", "--restart"])
        assert restarted.exit_code == 0
        _wait_for_service(base_url)
        state = runner.invoke(group, ["tx", "state"])
        assert state.exit_code == 0
        assert '"committed": []' in state.output
    finally:
        stopped = runner.invoke(group, ["self", "services", "flask-tx", "--stop"])
        assert stopped.exit_code == 0
        assert "stopped" in stopped.output.lower()


def test_flask_service_auto_restarts_on_unhealthy_status(tmp_path: Path) -> None:
    env_root = tmp_path / "env"
    env_root.mkdir()
    port = _reserve_port()
    base_url = f"http://127.0.0.1:{port}"
    _write_unhealthy_flask_service_plugin(env_root, port)

    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    runner = CliRunner()

    started = runner.invoke(group, ["self", "services", "flask-health", "--start"])
    assert started.exit_code == 0

    try:
        _wait_for_service(base_url)

        url_result = runner.invoke(group, ["healthsvc", "url"])
        assert url_result.exit_code == 0
        assert base_url in url_result.output

        fail_response = httpx.post(f"{base_url}/health/fail", timeout=1.0)
        fail_response.raise_for_status()

        unhealthy = httpx.get(f"{base_url}/health", timeout=1.0)
        assert unhealthy.status_code == 503

        status = runner.invoke(group, ["self", "services", "flask-health", "--status"])
        assert status.exit_code == 0
        assert "restarted" in status.output.lower()

        _wait_for_service(base_url)
        recovered = httpx.get(f"{base_url}/health/state", timeout=1.0)
        recovered.raise_for_status()
        assert recovered.json() == {"healthy": True}
    finally:
        stopped = runner.invoke(group, ["self", "services", "flask-health", "--stop"])
        assert stopped.exit_code == 0
        assert "stopped" in stopped.output.lower()