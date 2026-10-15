"""Consumer bindings to immutable, durably retained Saucepan outputs."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from filelock import FileLock, Timeout
from saucepan_sdk import Client, SaucepanError, TransportError

from zush.errors import IntegrationError
from zush.github import Repository
from zush.utils.state import atomic_write_text

PIN_POLICY = str(uuid5(NAMESPACE_URL, "zush:pin:until-released:v1"))
PIN_DEFINITION = {"uuid": PIN_POLICY, "type": "pin_policy", "retention": "until_released"}


def _external_client() -> Client:
    binary = os.environ.get("ZUSH_SAUCEPAN") or shutil.which("saucepan")
    if not binary:
        raise IntegrationError("Install Saucepan 0.10.x on PATH or set ZUSH_SAUCEPAN; then run saucepan init.")
    try:
        result = subprocess.run(  # noqa: S603 - explicit executable, no shell
            [binary, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise IntegrationError("Cannot run Saucepan; check ZUSH_SAUCEPAN and install Saucepan 0.10.x.") from error
    if result.returncode or not re.fullmatch(r"saucepan 0\.10\.\d+(?:[-+][\w.-]+)?\s*", result.stdout):
        raise IntegrationError("Unsupported Saucepan manager; install Saucepan 0.10.x.")
    return Client(executable=binary, root=os.environ.get("ZUSH_SAUCEPAN_ROOT") or None)


class SaucepanWorkspace:
    """No I/O during construction. The bindings file is consumer state, not a store."""

    def __init__(
        self,
        bindings: Path,
        *,
        client: Client | None = None,
        lock_timeout: float = 30,
        origin: Callable[[Repository], str] = lambda repo: f"https://github.com/{repo.target}.git",
    ) -> None:
        self.bindings = bindings
        self._client = client
        self._origin = origin
        self.lock_timeout = lock_timeout

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = _external_client()
        return self._client

    @contextmanager
    def _locked(self):
        self.bindings.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(str(self.bindings) + ".lock", timeout=self.lock_timeout):
                yield
        except Timeout as error:
            raise IntegrationError("Another Zush operation holds the bindings lock; retry when it finishes.") from error
        except SaucepanError as error:
            raise IntegrationError(
                f"Saucepan {error.code}; check the initialized root (saucepan init) and Git credentials. "
                "GitHub CLI authentication alone does not configure Git access. Previous selections were retained."
            ) from error
        except TransportError as error:
            raise IntegrationError(
                f"Saucepan transport {error.kind}; retry to reconcile the saved operation. "
                "Previous selections were retained."
            ) from error

    def _load(self) -> dict:
        if not self.bindings.exists():
            return {"consumer": str(uuid4()), "selected": {}, "pending": {}, "history": []}
        try:
            state = json.loads(self.bindings.read_text(encoding="utf-8"))
            if (
                not isinstance(state["consumer"], str)
                or not all(isinstance(state[key], dict) for key in ("selected", "pending"))
                or not isinstance(state["history"], list)
            ):
                raise ValueError
            return state
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise IntegrationError(
                f"Invalid Zush bindings at {self.bindings}; restore the state before continuing."
            ) from error

    def _save(self, state: dict) -> None:
        atomic_write_text(self.bindings, json.dumps(state, indent=2, sort_keys=True) + "\n")

    def ensure(self, repository: Repository) -> Path:
        with self._locked():
            state = self._load()
            previous = state["selected"].get(repository.target.casefold())
            if previous is not None:
                return self._path(previous)
            return self._prepare(state, repository)

    def installed(self, targets: set[str] | None = None) -> dict[str, Path]:
        with self._locked():
            return {
                key: self._path(binding)
                for key, binding in self._load()["selected"].items()
                if targets is None or key in targets
            }

    def update_all(self, repositories: Sequence[Repository]) -> None:
        with self._locked():
            state = self._load()
            for repository in repositories:
                if repository.target.casefold() in state["selected"]:
                    self._prepare(state, repository)

    def _path(self, binding: dict) -> Path:
        try:
            pin = self.client.pin(binding["pin_uuid"])
            output = pin["outputs"][binding["output_uuid"]]
            directory = Path(output["path"])
            if pin["state"] != "active" or not output["available"] or not directory.is_absolute():
                raise ValueError
            if not directory.is_dir():
                raise ValueError
            return directory
        except (KeyError, TypeError, ValueError) as error:
            raise IntegrationError("Selected output is not retained and available; refusing to execute it.") from error

    def _prepare(self, state: dict, repository: Repository) -> Path:
        target = repository.target.casefold()
        if not repository.commit or not re.fullmatch(r"[a-fA-F0-9]{40,64}", repository.commit):
            raise IntegrationError(f"GitHub did not provide an exact commit for {repository.target}.")
        pending = state["pending"].get(target)
        if pending is not None:
            # Complete a possibly committed operation before starting another one.
            self._finish(state, target, pending)
        previous = state["selected"].get(target)
        origin = self._origin(repository)
        if previous and previous["commit"] == repository.commit and previous["origin"] == origin:
            return self._path(previous)
        profile = self.client.profile("explicit-update")
        pending = {
            "commit": repository.commit,
            "origin": origin,
            "operation_key": f"zush:{state['consumer']}:{uuid4()}",
            # Save the expansion, not just a recipe name: recovery must adopt
            # precisely the same immutable policy definitions and references.
            "policy_catalog": profile["catalog"],
            "policy_refs": profile["combined_policy_refs"],
        }
        state["pending"][target] = pending
        self._save(state)
        return self._finish(state, target, pending)

    def _finish(self, state: dict, target: str, pending: dict) -> Path:
        self.client.register_policies([*pending["policy_catalog"], PIN_DEFINITION])
        if "group_uuid" not in pending:
            source = self.client.register_source({"type": "git", "origin": pending["origin"]})
            pending["source_uuid"] = source["uuid"]
            definition = {
                "registration_key": pending["operation_key"],
                "members": [
                    {
                        "name": "repository",
                        "target": {
                            "type": "acquire",
                            "source_uuid": source["uuid"],
                            "selector": {"type": "commit", "commit": pending["commit"]},
                            "policy_refs": pending["policy_refs"],
                        },
                    }
                ],
            }
            self._save(state)
            group = self.client.register_group(definition)
            self._validate_definition(group["definition"], pending)
            pending.update(group_uuid=group["uuid"], expected_revision=group["revision"])
            self._save(state)
        try:
            receipt = self.client.prepare_group(
                pending["group_uuid"],
                expected_revision=pending["expected_revision"],
                pin={"registration_key": pending["operation_key"], "policy_refs": [PIN_POLICY]},
            )
        except SaucepanError:
            # A definitive domain failure did not publish a new consumer binding.
            del state["pending"][target]
            self._save(state)
            raise
        binding = self._validate(receipt, pending)
        directory = self._path(binding)
        previous = state["selected"].get(target)
        if previous is not None:
            state["history"].append(previous)
        state["selected"][target] = binding
        del state["pending"][target]
        self._save(state)
        return directory

    def _validate(self, receipt: dict, pending: dict) -> dict:
        try:
            member = receipt["resources"]["members"]["repository"]
            group, pin = receipt["group"], receipt["pin"]
            self._validate_definition(group["definition"], pending)
            output_uuid = member["output_uuid"]
            entry = self.client.inspect(output_uuid)
            selected = group["selected"]["members"]["repository"]
            request = entry["request"]
            if (
                receipt["stale"]
                or group["uuid"] != pending["group_uuid"]
                or selected["output_uuid"] != output_uuid
                or pin["state"] != "active"
                or output_uuid not in pin["request"]["outputs"]
                or pin["request"]["registration_key"] != pending["operation_key"]
                or request["source_uuid"] != pending["source_uuid"]
                or request["selector"] != {"type": "commit", "commit": pending["commit"]}
                or entry["resolved"]["commit"] != pending["commit"]
                or entry["state"] != "ready"
            ):
                raise ValueError
            binding = {
                **pending,
                "group_revision": group["revision"],
                "output_uuid": output_uuid,
                "pin_uuid": pin["uuid"],
            }
            if Path(member["directory"]).resolve() != self._path(binding).resolve():
                raise ValueError
            return binding
        except (KeyError, TypeError, ValueError) as error:
            raise IntegrationError("Invalid retained output receipt; previous selection preserved.") from error

    @staticmethod
    def _validate_definition(definition: dict, pending: dict) -> None:
        try:
            members = definition["members"]
            member = members[0]
            target = member["target"]
            if (
                len(members) != 1
                or member["name"] != "repository"
                or member.get("relative")
                or definition["registration_key"] != pending["operation_key"]
                or definition.get("policy_refs")
                or target["type"] != "acquire"
                or target.get("claim")
                or target["source_uuid"] != pending["source_uuid"]
                or target["selector"] != {"type": "commit", "commit": pending["commit"]}
                or target["policy_refs"] != pending["policy_refs"]
                or any(value for key, value in target.get("selection", {}).items() if key != "format")
                or target.get("selection", {}).get("format", "natural") != "natural"
            ):
                raise ValueError
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise IntegrationError("Group registration returned conflicting repository provenance.") from error
