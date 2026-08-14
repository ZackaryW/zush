from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from zush.errors import ZushError
from zush.utils.addressing import Address
from zush.utils.config import (
    Alias,
    Configuration,
    bind,
    load_local_overlay,
    load_remote_map,
    merge_configuration,
    unbind,
)


class ConfigurationTests(unittest.TestCase):
    def test_remote_toml_preserves_typed_defaults_and_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.toml"
            path.write_text(
                """
[commands.hello]
target = { owner = "~", repo = "tools", path = "scripts.hello" }
default_args = ["base"]
default_map = { count = 2, enabled = true }

[namespaces.alice]
exclude = ["archive-*"]
""".strip(),
                encoding="utf-8",
            )
            config = load_remote_map(path)
            self.assertEqual(config.commands["hello"].target, Address(None, "tools", ("scripts", "hello")))
            self.assertEqual(config.commands["hello"].default_map, {"count": 2, "enabled": True})
            self.assertEqual(config.exclusions, {"alice": ("archive-*",)})

    def test_local_binding_wins_and_unbind_hides_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "aliases.json"
            remote_alias = Alias(Address(None, "remote", ("hello",)))
            local_alias = Alias(Address(None, "local", ("hello",)), ("base",), {"count": 3})
            remote = Configuration({"hello": remote_alias}, {})

            bind(path, "hello", local_alias)
            merged = merge_configuration(remote, load_local_overlay(path))
            self.assertEqual(merged.commands["hello"], local_alias)

            unbind(path, "hello")
            merged = merge_configuration(remote, load_local_overlay(path))
            self.assertNotIn("hello", merged.commands)

    def test_invalid_remote_shape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.toml"
            path.write_text('[commands.bad]\ntarget = { owner = "~" }', encoding="utf-8")
            with self.assertRaises(ZushError):
                load_remote_map(path)
