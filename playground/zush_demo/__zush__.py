"""Playground plugin: simulates a zush plugin for testing behavior."""

import click


class ZushPlugin:
    """Demo plugin with a single command."""

    def __init__(self) -> None:
        self.commands = {
            "demo": click.Group("demo", help="Demo plugin commands"),
            "shared": click.Group("shared", help="Shared group (other plugins can append under it)"),
        }
        greet_cmd = click.Command("greet", callback=_greet_cb, help="Say hello from the playground")
        self.commands["demo.greet"] = greet_cmd
        # Command under shared so the group is "owned" by this plugin first
        self.commands["shared.hello"] = click.Command(
            "hello", callback=_shared_hello_cb, help="From zush_demo"
        )


def _greet_cb() -> None:
    click.echo("Hello from playground zush_demo!")


def _shared_hello_cb() -> None:
    click.echo("ZUSH_SHARED_HELLO_FROM_DEMO")


ZushPlugin = ZushPlugin()
