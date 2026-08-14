from __future__ import annotations

from dataclasses import dataclass

from zush.errors import ZushError


@dataclass(frozen=True)
class Address:
    owner: str | None
    repository: str
    script: tuple[str, ...]


def parse_address(value: str) -> Address:
    target, separator, script_path = value.partition(":")
    if not separator or not target or not script_path:
        raise ZushError("addresses use ~repo:path.to.script or owner/repo:path.to.script")

    if target.startswith("~"):
        if "/" in target or target == "~":
            raise ZushError("current-owner addresses use ~repo:path.to.script")
        owner = None
        repository = target[1:]
    else:
        if target.count("/") != 1:
            raise ZushError("external addresses use owner/repo:path.to.script")
        owner, repository = target.split("/", 1)

    segments = tuple(script_path.split("."))
    components = (owner or "~", repository, *segments)
    if any(not component for component in components):
        raise ZushError("address components must not be empty")
    if any(component in {".", ".."} or "/" in component or "\\" in component for component in components):
        raise ZushError("address components must not contain traversal or path separators")
    return Address(owner, repository, segments)


def format_target(address: Address, current_owner: str) -> str:
    owner = address.owner or current_owner
    if not owner:
        raise ZushError("GitHub authentication did not provide an owner login")
    return f"{owner}/{address.repository}"
