from __future__ import annotations

import argparse
import sys
from importlib.metadata import version

from zush.application import Application, Invocation
from zush.errors import ZushError
from zush.github import GitHubClient
from zush.utils.paths import ZushPaths


def create_application() -> Application:
    return Application(ZushPaths.from_environment(), GitHubClient())


def run_cli(argv: list[str], app: Application | None = None) -> int:
    application = app or create_application()
    try:
        if not argv or argv[0] in {"-h", "--help"}:
            _print_help()
            return 0
        if argv == ["--version"]:
            print(f"zush {version('zush')}")
            return 0
        if argv[0] == "namespace":
            return _namespace(argv[1:], application)
        if argv[0] == "alias":
            return _alias(argv[1:], application)
        if argv[0] == "run":
            name, invocation = _parse_invocation(argv[1:], "zush run")
            return application.execute_alias(name, invocation)
        if argv[0] == "update":
            if len(argv) != 1:
                raise ZushError("zush update takes no arguments")
            application.update()
            return 0
        target, invocation = _parse_invocation(argv, "zush")
        return application.execute(target, invocation)
    except ZushError as error:
        print(f"zush: {error}", file=sys.stderr)
        return error.exit_code


def main(argv: list[str] | None = None) -> int:
    return run_cli(list(sys.argv[1:] if argv is None else argv))


def _namespace(argv: list[str], app: Application) -> int:
    parser = argparse.ArgumentParser(prog="zush namespace", add_help=False)
    subparsers = parser.add_subparsers(dest="action", required=True)
    add = subparsers.add_parser("add", add_help=False)
    add.add_argument("owner")
    subparsers.add_parser("list", add_help=False)
    remove = subparsers.add_parser("remove", add_help=False)
    remove.add_argument("owner")
    try:
        values = parser.parse_args(argv)
    except SystemExit as error:
        raise ZushError("namespace commands are add <owner>, list, or remove <owner>") from error
    if values.action == "add":
        app.add_namespace(values.owner)
    elif values.action == "remove":
        app.remove_namespace(values.owner)
    else:
        for owner in app.list_namespaces():
            print(owner)
    return 0


def _alias(argv: list[str], app: Application) -> int:
    parser = argparse.ArgumentParser(prog="zush alias", add_help=False)
    subparsers = parser.add_subparsers(dest="action", required=True)
    bind_parser = subparsers.add_parser("bind", add_help=False)
    bind_parser.add_argument("name")
    bind_parser.add_argument("target")
    unbind_parser = subparsers.add_parser("unbind", add_help=False)
    unbind_parser.add_argument("name")
    try:
        values = parser.parse_args(argv)
    except SystemExit as error:
        raise ZushError("alias commands are bind <name> <target> or unbind <name>") from error
    if values.action == "bind":
        app.bind_alias(values.name, values.target)
    else:
        app.unbind_alias(values.name)
    return 0


def _parse_invocation(argv: list[str], program: str) -> tuple[str, Invocation]:
    if "--" in argv:
        boundary = argv.index("--")
        options = argv[:boundary]
        raw = argv[boundary + 1 :]
    else:
        options = argv
        raw = []
    parser = argparse.ArgumentParser(prog=program, add_help=False)
    parser.add_argument("target")
    parser.add_argument("--arg", action="append", default=[])
    parser.add_argument("--map", dest="maps", action="append", default=[])
    parser.add_argument("--var", dest="variables", action="append", default=[])
    parser.add_argument("--casted", action="append", default=[])
    try:
        values = parser.parse_args(options)
    except SystemExit as error:
        raise ZushError(f"{program} requires a target followed by invocation options") from error
    invocation = Invocation(
        args=(*values.arg, *raw),
        maps=tuple(values.maps),
        variables=tuple(values.variables),
        casted=tuple(values.casted),
    )
    return values.target, invocation


def _print_help() -> None:
    print(
        "usage: zush ADDRESS [options] [-- argv...]\n"
        "       zush run ALIAS [options] [-- argv...]\n"
        "       zush namespace {add,list,remove}\n"
        "       zush alias {bind,unbind}\n"
        "       zush update"
    )
