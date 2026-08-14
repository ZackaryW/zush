"""Shared isolated scenario lifecycle."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def before_scenario(context, _scenario) -> None:
    context.zush_workdir = Path(tempfile.mkdtemp(prefix="zush-behave-"))
    context.zush_statements = []


def after_scenario(context, _scenario) -> None:
    shutil.rmtree(context.zush_workdir, ignore_errors=True)
