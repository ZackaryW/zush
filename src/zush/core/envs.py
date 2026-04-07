"""Helpers for resolving environments (e.g. current interpreter's site-packages)."""

from __future__ import annotations

from pathlib import Path

import site
import sysconfig

from zush.utils.envs import dedupe_paths as _dedupe_paths


def current_site_package_dirs() -> list[Path]:
    """Return directories that represent the current interpreter's site-packages."""
    candidates: list[Path] = []

    try:
        for raw_path in site.getsitepackages():
            path = Path(raw_path)
            if path.is_dir():
                candidates.append(path)
    except Exception:
        pass

    try:
        discovered_paths = sysconfig.get_paths()
    except Exception:
        discovered_paths = {}
    for key in ("purelib", "platlib"):
        raw_path = discovered_paths.get(key)
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.is_dir():
            candidates.append(path)

    try:
        user_site = site.getusersitepackages()
    except Exception:
        user_site = None
    if user_site:
        path = Path(user_site)
        if path.is_dir():
            candidates.append(path)

    return _dedupe_paths(candidates)
