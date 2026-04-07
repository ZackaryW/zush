"""Playground plugin: simulates a zush plugin for testing behavior."""

import click

from zush.pluginloader.plugin import Plugin


def _greet_cb() -> None:
    click.echo("Hello from playground zush_demo!")


def _shared_hello_cb() -> None:
    click.echo("ZUSH_SHARED_HELLO_FROM_DEMO")


p = Plugin()
p.group("demo", help="Demo plugin commands").command(
    "greet", callback=_greet_cb, help="Say hello from the playground"
)
p.group("shared", help="Shared group (other plugins can append under it)").command(
    "hello", callback=_shared_hello_cb, help="From zush_demo"
)

ZushPlugin = p
