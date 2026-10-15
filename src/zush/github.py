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
            argv, check=False, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as error:
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
        # gh repo list exposes the default branch NAME, not its commit oid.
        # Request exact commit evidence directly, paging without cloning anything.
        query = """query($owner:String!,$cursor:String) {
          repositoryOwner(login:$owner) {
            repositories(first:100,after:$cursor,ownerAffiliations:[OWNER],orderBy:{field:NAME,direction:ASC}) {
              nodes { name nameWithOwner description defaultBranchRef { target { oid } } }
              pageInfo { hasNextPage endCursor }
            }
          }
        }"""
        repositories: list[Repository] = []
        cursor = None
        seen = set()
        while True:
            argv = ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}"]
            if cursor:
                argv.extend(["-f", f"cursor={cursor}"])
            payload = self._json(argv)
            try:
                connection = payload["data"]["repositoryOwner"]["repositories"]
                nodes, page = connection["nodes"], connection["pageInfo"]
                if payload.get("errors") or not isinstance(nodes, list):
                    raise TypeError
                repositories.extend(self._records(owner, nodes))
                if not isinstance(page["hasNextPage"], bool):
                    raise TypeError
                if not page["hasNextPage"]:
                    break
                cursor = page["endCursor"]
                if not isinstance(cursor, str) or not cursor or cursor in seen:
                    raise TypeError
                seen.add(cursor)
            except (KeyError, TypeError) as error:
                raise ZushError(f"invalid GitHub repository page for {owner}") from error
        return repositories

    @staticmethod
    def _records(owner: str, nodes: list) -> list[Repository]:
        repositories = []
        for entry in nodes:
            try:
                # Empty repositories have no commit to materialize.
                if entry["defaultBranchRef"] is None:
                    continue
                name = entry["name"]
                full_name = entry["nameWithOwner"]
                branch = entry["defaultBranchRef"]
                commit = branch["target"]["oid"]
                description = entry.get("description") or ""
                if (
                    not isinstance(name, str)
                    or not isinstance(full_name, str)
                    or full_name.casefold() != f"{owner}/{name}".casefold()
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
