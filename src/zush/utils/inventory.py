from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from zush.errors import ZushError
from zush.github import Repository
from zush.utils.state import atomic_write_text


def generated_identity(owner: str, repository: str) -> str:
    return f"{owner}--{repository}"


def build_bucket(repositories: Iterable[Repository]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for repository in sorted(repositories, key=lambda item: item.target.casefold()):
        if not repository.commit:
            raise ZushError(f"repository {repository.target} has no default-branch commit")
        identity = generated_identity(repository.owner, repository.name)
        manifest = {
            "name": identity,
            "version": repository.commit,
            "description": repository.description or f"Managed Zush repository {repository.target}",
        }
        result.append(
            {
                "name": identity,
                "version": repository.commit,
                "url": repository.target,
                "ref": repository.commit,
                "manifest": manifest,
            }
        )
    return result


def write_bucket(path: Path, repositories: Iterable[Repository]) -> None:
    atomic_write_text(path, json.dumps(build_bucket(repositories), indent=2, sort_keys=True) + "\n")
