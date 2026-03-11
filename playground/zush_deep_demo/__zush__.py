"""Playground plugin: deep command tree (nested groups) to verify zush supports arbitrary nesting.

Invocation: zush deep a b c d leaf
"""

import click

# Markers for tests
DEEP_LEAF_MARKER = "ZUSH_DEEP_LEAF_OK"
SHARED_APPENDED_MARKER = "ZUSH_SHARED_APPENDED_FROM_DEEP"


def _leaf_cb() -> None:
    click.echo(DEEP_LEAF_MARKER)


def _shared_appended_cb() -> None:
    click.echo(SHARED_APPENDED_MARKER)


class ZushPlugin:
    def __init__(self) -> None:
        # Deep tree: deep -> a -> b -> c -> d -> leaf
        commands = {
            "deep": click.Group("deep", help="Deep nesting demo"),
            "deep.a": click.Group("a", help="Level a"),
            "deep.a.b": click.Group("b", help="Level b"),
            "deep.a.b.c": click.Group("c", help="Level c"),
            "deep.a.b.c.d": click.Group("d", help="Level d"),
            "deep.a.b.c.d.leaf": click.Command(
                "leaf",
                callback=_leaf_cb,
                help="Leaf command at depth 5",
            ),
        }
        # Append under a group created by another plugin (zush_demo has "shared" + "shared.hello")
        commands["shared.nested"] = click.Group("nested", help="From deep_demo under shared")
        commands["shared.nested.from"] = click.Group("from", help="Appended branch")
        commands["shared.nested.from.deep"] = click.Group("deep", help="Appended group")
        commands["shared.nested.from.deep.run"] = click.Command(
            "run",
            callback=_shared_appended_cb,
            help="Command appended under shared by another plugin",
        )
        self.commands = commands


ZushPlugin = ZushPlugin()
