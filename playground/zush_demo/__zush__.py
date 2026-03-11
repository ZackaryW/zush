"""Playground plugin: simulates a zush plugin for testing behavior."""

import click


class ZushPlugin:
    """Demo plugin with a single command."""

    def __init__(self) -> None:
        self.commands = {
            "demo": click.Group("demo", help="Demo plugin commands"),
        }
        # Add a subcommand under demo
        greet_cmd = click.Command("greet", callback=_greet_cb, help="Say hello from the playground")
        self.commands["demo.greet"] = greet_cmd


def _greet_cb() -> None:
    click.echo("Hello from playground zush_demo!")


ZushPlugin = ZushPlugin()
