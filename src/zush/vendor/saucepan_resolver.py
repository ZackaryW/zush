"""Vendored Saucepan Python platform resolver.

Source: saucepan/resolvers/python/saucepan_resolver.py at the v0.3.0 contract.
"""

from __future__ import annotations

import os
import platform
import stat
import urllib.request

OWNER = "ZackaryW"
REPO = "saucepan"

_ASSET_NAMES = {
    ("Darwin", "arm64"): "saucepan-aarch64-apple-darwin",
    ("Darwin", "x86_64"): "saucepan-x86_64-apple-darwin",
    ("Windows", "AMD64"): "saucepan-x86_64-pc-windows-msvc.exe",
    ("Windows", "ARM64"): "saucepan-aarch64-pc-windows-msvc.exe",
    ("Windows", "x86"): "saucepan-i686-pc-windows-msvc.exe",
    ("Linux", "x86_64"): "saucepan-x86_64-unknown-linux-musl",
}


def _asset_name(system: str | None = None, machine: str | None = None) -> str:
    key = (system or platform.system(), machine or platform.machine())
    try:
        return _ASSET_NAMES[key]
    except KeyError as error:
        raise RuntimeError(f"no saucepan release asset for platform {key}") from error


def resolve(version: str, dest: str | None = None) -> str:
    if not version:
        raise ValueError("resolve() requires an explicit version")
    asset = _asset_name()
    url = f"https://github.com/{OWNER}/{REPO}/releases/download/{version}/{asset}"
    destination = dest or asset
    urllib.request.urlretrieve(url, destination)
    if platform.system() != "Windows":
        mode = os.stat(destination).st_mode
        os.chmod(destination, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return destination
