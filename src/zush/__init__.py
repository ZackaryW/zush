"""Zush package entrypoints."""

from zush.core.bootstrap import create_zush_group, main

from zush.plugin import Plugin #noqa

__all__ = ["create_zush_group", "main"]
