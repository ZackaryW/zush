from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from zush.errors import ZushError
from zush.github import GitHubClient, Repository
from zush.saucepan import SaucepanWorkspace
from zush.utils.addressing import Address, format_target, parse_address
from zush.utils.config import (
    Alias,
    Configuration,
    bind,
    load_local_overlay,
    load_remote_map,
    merge_configuration,
    unbind,
)
from zush.utils.inventory import write_bucket
from zush.utils.paths import ZushPaths
from zush.utils.scripts import resolve_script, runner_argv
from zush.utils.state import load_namespaces, save_namespaces
from zush.utils.structured import build_payload, input_environment


class Workspace(Protocol):
    def ensure(self, target: str) -> Path: ...

    def register_index(self, path: Path) -> None: ...

    def update_all(self, visible_targets: set[str]) -> None: ...


ProcessRunner = Callable[[list[str], dict[str, str]], int]


@dataclass(frozen=True)
class Invocation:
    args: tuple[str, ...] = ()
    maps: tuple[str, ...] = ()
    variables: tuple[str, ...] = ()
    casted: tuple[str, ...] = ()


def _run_process(argv: list[str], environment: dict[str, str]) -> int:
    completed = subprocess.run(argv, env=environment, check=False)  # noqa: S603 - explicit runner argv
    return completed.returncode


class Application:
    def __init__(
        self,
        paths: ZushPaths,
        github: GitHubClient,
        workspace: Workspace | None = None,
        *,
        run_process: ProcessRunner = _run_process,
    ) -> None:
        self.paths = paths
        self.github = github
        self._workspace = workspace
        self._run_process = run_process

    @property
    def workspace(self) -> Workspace:
        if self._workspace is None:
            self._workspace = SaucepanWorkspace(self.paths.saucepan, binary_destination=self.paths.binary)
        return self._workspace

    def add_namespace(self, owner: str) -> None:
        if not owner or "/" in owner or any(character.isspace() for character in owner):
            raise ZushError("namespace owner must be one GitHub login")
        self.github.repositories(owner)
        current = self.github.current_login()
        if owner == current:
            return
        owners = load_namespaces(self.paths.namespaces)
        owners.add(owner)
        save_namespaces(self.paths.namespaces, owners)

    def list_namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(load_namespaces(self.paths.namespaces), key=str.casefold))

    def remove_namespace(self, owner: str) -> None:
        owners = load_namespaces(self.paths.namespaces)
        owners.discard(owner)
        save_namespaces(self.paths.namespaces, owners)

    def bind_alias(self, name: str, target: str) -> None:
        bind(self.paths.aliases, name, Alias(parse_address(target)))

    def unbind_alias(self, name: str) -> None:
        unbind(self.paths.aliases, name)

    def execute(self, target: str, invocation: Invocation) -> int:
        address = parse_address(target)
        current, current_repositories, configuration = self._base_context()
        return self._execute_address(address, invocation, current, current_repositories, configuration)

    def execute_alias(self, name: str, invocation: Invocation) -> int:
        current, current_repositories, configuration = self._base_context()
        alias = configuration.commands.get(name)
        if alias is None:
            raise ZushError(f"unknown alias: {name}")
        combined = Invocation(
            args=(*alias.default_args, *invocation.args),
            maps=invocation.maps,
            variables=invocation.variables,
            casted=invocation.casted,
        )
        return self._execute_address(
            alias.target,
            combined,
            current,
            current_repositories,
            configuration,
            defaults=alias.default_map,
        )

    def update(self) -> None:
        current = self.github.current_login()
        repositories = list(self.github.repositories(current))
        for owner in self.list_namespaces():
            repositories.extend(self.github.repositories(owner))
        self._refresh_index(repositories)
        configuration = self._load_configuration(current, repositories)
        visible = {
            repository.target
            for repository in repositories
            if not self._excluded(configuration, repository.owner, repository.name)
        }
        self.workspace.update_all(visible)

    def _base_context(self) -> tuple[str, list[Repository], Configuration]:
        current = self.github.current_login()
        repositories = self.github.repositories(current)
        self._refresh_index(repositories)
        configuration = self._load_configuration(current, repositories)
        return current, repositories, configuration

    def _load_configuration(self, current: str, repositories: Sequence[Repository]) -> Configuration:
        config_repository = next(
            (repository for repository in repositories if repository.owner == current and repository.name == ".zush"),
            None,
        )
        remote_path: Path | None = None
        if config_repository is not None:
            remote_path = self.workspace.ensure(config_repository.target) / "map.toml"
        return merge_configuration(load_remote_map(remote_path), load_local_overlay(self.paths.aliases))

    def _execute_address(
        self,
        address: Address,
        invocation: Invocation,
        current: str,
        current_repositories: list[Repository],
        configuration: Configuration,
        *,
        defaults: dict[str, object] | object = None,
    ) -> int:
        owner = address.owner or current
        if owner != current and owner not in load_namespaces(self.paths.namespaces):
            raise ZushError(f"namespace is not enrolled: {owner}")
        owner_repositories = current_repositories if owner == current else self.github.repositories(owner)
        repositories = list(current_repositories)
        if owner != current:
            repositories.extend(owner_repositories)
        self._refresh_index(repositories)
        if self._excluded(configuration, owner, address.repository):
            raise ZushError(f"repository is excluded: {owner}/{address.repository}")
        repository = next((item for item in owner_repositories if item.name == address.repository), None)
        if repository is None:
            raise ZushError(f"repository is not visible: {owner}/{address.repository}")
        checkout = self.workspace.ensure(format_target(address, current))
        script = resolve_script(checkout, address.script)
        payload = build_payload(
            defaults if isinstance(defaults, dict) else {}, invocation.maps, invocation.variables, invocation.casted
        )
        argv = runner_argv(script, invocation.args)
        with input_environment(payload) as environment:
            return self._run_process(argv, environment)

    def _refresh_index(self, repositories: Sequence[Repository]) -> None:
        unique = {repository.target: repository for repository in repositories}
        write_bucket(self.paths.bucket, unique.values())
        self.workspace.register_index(self.paths.bucket)

    @staticmethod
    def _excluded(configuration: Configuration, owner: str, repository: str) -> bool:
        return any(fnmatch.fnmatchcase(repository, pattern) for pattern in configuration.exclusions.get(owner, ()))
