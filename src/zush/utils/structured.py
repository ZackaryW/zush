from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from zush.errors import ZushError

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")


def parse_map(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ZushError(f"invalid JSON map: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise ZushError("--map requires a JSON object")
    return parsed


def parse_var(value: str) -> tuple[str, str]:
    key, separator, raw = value.partition("=")
    if not separator or not _KEY.fullmatch(key):
        raise ZushError("--var requires key=value with a valid key")
    return key, raw


def parse_casted(value: str) -> tuple[str, object]:
    type_name, plus, assignment = value.partition("+")
    if not plus:
        raise ZushError("--casted requires type+key=value")
    key, raw = parse_var(assignment)
    try:
        if type_name == "str":
            converted: object = raw
        elif type_name == "int":
            converted = int(raw)
        elif type_name == "float":
            converted = float(raw)
        elif type_name == "bool":
            if raw not in {"true", "false"}:
                raise ValueError
            converted = raw == "true"
        elif type_name == "json":
            converted = json.loads(raw)
        else:
            raise ZushError(f"unsupported cast type: {type_name}")
    except (ValueError, json.JSONDecodeError) as error:
        raise ZushError(f"cannot cast {key} as {type_name}") from error
    return key, converted


def build_payload(
    defaults: Mapping[str, object],
    maps: Sequence[str],
    variables: Sequence[str],
    casted: Sequence[str],
) -> dict[str, object]:
    payload = dict(defaults)
    for value in maps:
        payload.update(parse_map(value))
    for value in variables:
        key, parsed = parse_var(value)
        payload[key] = parsed
    for value in casted:
        key, parsed = parse_casted(value)
        payload[key] = parsed
    return payload


@contextmanager
def input_environment(payload: Mapping[str, object], base: Mapping[str, str] | None = None) -> Iterator[dict[str, str]]:
    environment = dict(os.environ if base is None else base)
    environment.pop("ZUSH_INPUT_FILE", None)
    if not payload:
        yield environment
        return
    descriptor, name = tempfile.mkstemp(prefix="zush-input-", suffix=".json")
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(dict(payload), stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        environment["ZUSH_INPUT_FILE"] = str(path)
        yield environment
    finally:
        path.unlink(missing_ok=True)
