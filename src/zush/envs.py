"""Helpers for resolving environments (e.g. current interpreter's site-packages)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import site
import sysconfig


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(rp)
    return out


def current_site_package_dirs() -> list[Path]:
    """Return directories that represent the current interpreter's site-packages.

    This is intentionally implementation-agnostic so that uv / virtualenv / venv
    can all be supported. Resolution strategy:

    1. site.getsitepackages() (when available) – global site-packages.
    2. sysconfig.get_paths() purelib / platlib – env-local package dirs.
    3. site.getusersitepackages() – user site-packages.

    Only existing directories are returned, and duplicates are removed.
    """
    candidates: list[Path] = []

    # 1) site.getsitepackages()
    try:
        for p in site.getsitepackages():
            pp = Path(p)
            if pp.is_dir():
                candidates.append(pp)
    except Exception:
        # Not available or fails; ignore.
        pass

    # 2) sysconfig purelib / platlib
    try:
        paths = sysconfig.get_paths()
    except Exception:
        paths = {}
    for key in ("purelib", "platlib"):
        value = paths.get(key)
        if not value:
            continue
        pp = Path(value)
        if pp.is_dir():
            candidates.append(pp)

    # 3) user site
    try:
        user = site.getusersitepackages()
    except Exception:
        user = None
    if user:
        up = Path(user)
        if up.is_dir():
            candidates.append(up)

    return _dedupe_paths(candidates)

