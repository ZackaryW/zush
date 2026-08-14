from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from zush.errors import IntegrationError, ZushError

CommandRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class Repository:
    owner: str
    name: str
    commit: str
    description: str

    @property
    def target(self) -> str:
        return f"{self.owner}/{self.name}"


def _run(argv: list[str]) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argv, never a shell command
            argv, check=False, capture_output=True, text=True
        )
    except OSError as error:
        raise IntegrationError(f"cannot run GitHub CLI: {error}") from error
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "GitHub CLI failed"
        raise IntegrationError(detail)
    return completed.stdout


class GitHubClient:
    def __init__(self, run: CommandRunner = _run) -> None:
        self._run = run

    def current_login(self) -> str:
        payload = self._json(["gh", "api", "user"])
        if not isinstance(payload, dict) or not isinstance(payload.get("login"), str) or not payload["login"]:
            raise ZushError("GitHub authentication did not return a login")
        return payload["login"]

    def repositories(self, owner: str) -> list[Repository]:
        payload = self._json(
            [
                "gh",
                "repo",
                "list",
                owner,
                "--limit",
                "1000",
                "--json",
                "name,nameWithOwner,description,defaultBranchRef",
            ]
        )
        if not isinstance(payload, list):
            raise ZushError(f"GitHub repository listing for {owner} is not an array")
        repositories: list[Repository] = []
        for entry in payload:
            try:
                name = entry["name"]
                full_name = entry["nameWithOwner"]
                branch = entry["defaultBranchRef"]
                commit = branch["oid"]
                description = entry.get("description") or ""
                if (
                    not isinstance(name, str)
                    or not isinstance(full_name, str)
                    or full_name != f"{owner}/{name}"
                    or not isinstance(commit, str)
                    or not commit
                    or not isinstance(description, str)
                ):
                    raise TypeError
            except (KeyError, TypeError) as error:
                raise ZushError(f"invalid repository record returned for {owner}") from error
            repositories.append(Repository(owner, name, commit, description))
        return repositories

    def _json(self, argv: list[str]) -> object:
        try:
            return json.loads(self._run(argv))
        except json.JSONDecodeError as error:
            raise ZushError("GitHub CLI returned invalid JSON") from error
