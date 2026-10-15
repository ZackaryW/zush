from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from zush.errors import ZushError

SUPPORTED_SUFFIXES = (".py", ".ps1", ".sh", ".cmd", ".bat")


def resolve_script(root: Path, segments: tuple[str, ...]) -> Path:
    invalid = any(not segment or segment in {".", ".."} or "/" in segment or "\\" in segment for segment in segments)
    if not segments or invalid:
        raise ZushError("invalid script path")
    resolved_root = root.resolve()
    base = resolved_root.joinpath(*segments)
    if not base.is_relative_to(resolved_root):
        raise ZushError("script path escapes the managed checkout")
    candidates: list[Path] = []
    if base.is_file() and (base.suffix.casefold() in SUPPORTED_SUFFIXES or os.access(base, os.X_OK)):
        candidates.append(base)
    candidates.extend(candidate for suffix in SUPPORTED_SUFFIXES if (candidate := base.with_suffix(suffix)).is_file())
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        raise ZushError(f"unknown script: {'.'.join(segments)}")
    if len(candidates) > 1:
        names = ", ".join(str(candidate.relative_to(resolved_root)) for candidate in candidates)
        raise ZushError(f"ambiguous script; candidates: {names}")
    selected = candidates[0].resolve()
    if not selected.is_relative_to(resolved_root):
        raise ZushError("script path escapes the managed checkout")
    return selected


def runner_argv(
    script: Path,
    args: Sequence[str],
    which: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    script_value = str(script)
    suffix = script.suffix.casefold()
    if suffix == ".py":
        return [sys.executable, script_value, *args]
    if suffix == ".ps1":
        runner = which("pwsh") or which("powershell")
        if runner is None:
            raise ZushError("PowerShell runner is not available")
        return [runner, "-File", script_value, *args]
    if suffix == ".sh":
        runner = which("sh") or which("bash")
        if runner is None:
            raise ZushError("POSIX shell runner is not available")
        return [runner, script_value, *args]
    if suffix in {".cmd", ".bat"}:
        runner = which("cmd") or os.environ.get("COMSPEC")
        if runner is None:
            raise ZushError("Windows command processor is not available")
        return [runner, "/d", "/s", "/c", script_value, *args]
    if script.is_file() and os.access(script, os.X_OK):
        return [script_value, *args]
    raise ZushError(f"unsupported script type: {script.name}")
