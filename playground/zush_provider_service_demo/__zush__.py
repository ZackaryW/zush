from __future__ import annotations

import click

from zush.core.runtime import g
from zush.core.services import read_service_registry
from zush.pluginloader.plugin import Plugin


SERVICE_NAME = "provider-demo"


class ProviderServiceControl:
    def start(self, runtime):
        runtime.state["running"] = True
        runtime.state["boot_count"] = int(runtime.state.get("boot_count", 0)) + 1
        runtime.save()
        return f"started {SERVICE_NAME}"

    def stop(self, runtime):
        runtime.state["running"] = False
        runtime.save()
        return f"stopped {SERVICE_NAME}"

    def restart(self, runtime):
        self.stop(runtime)
        return self.start(runtime).replace("started", "restarted", 1)

    def status(self, runtime):
        return "healthy" if runtime.state.get("running") else "stopped"


class ControlSurface:
    def __init__(self, runtime) -> None:
        self._runtime = runtime

    def describe(self) -> str:
        registry = read_service_registry(self._runtime.storage)
        state = registry.get("services", {}).get(SERVICE_NAME, {})
        boot_count = int(state.get("boot_count", 0))
        status = self._runtime.status_service(SERVICE_NAME)
        return f"{SERVICE_NAME} boot={boot_count} status={status}"


def build_provider(runtime) -> ControlSurface:
    return ControlSurface(runtime)


@click.command("info")
def info_cmd() -> None:
    click.echo(g["provider_control"].describe())


@click.command("start")
def start_cmd() -> None:
    click.echo(ZushPlugin.runtime.start_service(SERVICE_NAME))


@click.command("stop")
def stop_cmd() -> None:
    click.echo(ZushPlugin.runtime.stop_service(SERVICE_NAME))


@click.command("restart")
def restart_cmd() -> None:
    click.echo(ZushPlugin.runtime.restart_service(SERVICE_NAME))


@click.command("status")
def status_cmd() -> None:
    click.echo(ZushPlugin.runtime.status_service(SERVICE_NAME))


p = Plugin()
p.service(SERVICE_NAME, ["provider-demo"], control=ProviderServiceControl())
p.provide_factory(
    "provider_control",
    build_provider,
    service=SERVICE_NAME,
    recreate_on_restart=True,
)
provider = p.group("provider", help="Provider-owned service demo")
provider.command("info", callback=info_cmd.callback)
provider.command("start", callback=start_cmd.callback)
provider.command("stop", callback=stop_cmd.callback)
provider.command("restart", callback=restart_cmd.callback)
provider.command("status", callback=status_cmd.callback)
ZushPlugin = p