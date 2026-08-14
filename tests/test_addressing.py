from __future__ import annotations

import unittest

from zush.errors import ZushError
from zush.utils.addressing import Address, format_target, parse_address


class AddressingTests(unittest.TestCase):
    def test_current_owner_address(self) -> None:
        address = parse_address("~tools:release.publish")
        self.assertEqual(address, Address(None, "tools", ("release", "publish")))
        self.assertEqual(format_target(address, "alice"), "alice/tools")

    def test_external_owner_preserves_dotted_repository(self) -> None:
        address = parse_address("Pathverse/scripts.tools:release.publish")
        self.assertEqual(address, Address("Pathverse", "scripts.tools", ("release", "publish")))

    def test_invalid_addresses(self) -> None:
        for value in ("~tools.release", "~:hello", "alice/tools:", "tools:hello", "~/tools:hello", "~tools:../x"):
            with self.subTest(value=value), self.assertRaises(ZushError):
                parse_address(value)
