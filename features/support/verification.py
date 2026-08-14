"""Shared public-contract verification entry point."""

from __future__ import annotations

from features.support.public_contract import VERIFIERS


def record_statement(context, kind: str, text: str) -> None:
    context.zush_statements.append((kind, text))


def verify_scenario(context, capability: str) -> None:
    if getattr(context, "zush_verified", False):
        return
    VERIFIERS[capability](context.zush_workdir)
    context.zush_verified = True
