"""Playground plugin: deep command tree (nested groups) to verify zush supports arbitrary nesting.

Invocation: zush deep a b c d leaf
"""

import click

# Marker for tests to verify the leaf command ran
DEEP_LEAF_MARKER = "ZUSH_DEEP_LEAF_OK"


def _leaf_cb() -> None:
    click.echo(DEEP_LEAF_MARKER)


class ZushPlugin:
    def __init__(self) -> None:
        # Build a deep tree: deep -> a -> b -> c -> d -> leaf (5 levels of groups + 1 command)
        self.commands = {
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


ZushPlugin = ZushPlugin()
