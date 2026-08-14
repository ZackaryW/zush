from __future__ import annotations

import json
import unittest
from pathlib import Path

from zush.errors import ZushError
from zush.utils.structured import build_payload, input_environment, parse_casted, parse_map, parse_var


class StructuredTests(unittest.TestCase):
    def test_cast_matrix(self) -> None:
        cases = {
            "str+value=7": ("value", "7"),
            "int+value=7": ("value", 7),
            "float+value=1.5": ("value", 1.5),
            "bool+value=false": ("value", False),
            'json+value={"nested":true}': ("value", {"nested": True}),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_casted(value), expected)

    def test_invalid_inputs(self) -> None:
        for operation, value in (
            (parse_var, "missing"),
            (parse_casted, "decimal+value=1"),
            (parse_casted, "int+value=no"),
            (parse_map, "[]"),
        ):
            with self.subTest(value=value), self.assertRaises(ZushError):
                operation(value)

    def test_shallow_precedence(self) -> None:
        payload = build_payload(
            {"nested": {"old": 1}, "region": "default"},
            ['{"nested":{"new":2},"map_only":true}'],
            ["region=west"],
            ["float+threshold=1.5"],
        )
        self.assertEqual(
            payload,
            {"nested": {"new": 2}, "region": "west", "map_only": True, "threshold": 1.5},
        )

    def test_input_file_is_typed_and_cleaned_up(self) -> None:
        seen: Path | None = None
        with input_environment({"enabled": False, "count": 2}, {"BASE": "yes"}) as environment:
            self.assertEqual(environment["BASE"], "yes")
            seen = Path(environment["ZUSH_INPUT_FILE"])
            self.assertEqual(json.loads(seen.read_text(encoding="utf-8")), {"enabled": False, "count": 2})
        self.assertIsNotNone(seen)
        self.assertFalse(seen.exists())

    def test_empty_payload_does_not_set_environment_key(self) -> None:
        with input_environment({}, {}) as environment:
            self.assertNotIn("ZUSH_INPUT_FILE", environment)
