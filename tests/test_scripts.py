from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from zush.errors import ZushError
from zush.utils.scripts import resolve_script, runner_argv


class ScriptTests(unittest.TestCase):
    def test_inferred_and_exact_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inferred = root / "tasks" / "cleanup.py"
            inferred.parent.mkdir()
            inferred.write_text("print('ok')", encoding="utf-8")
            self.assertEqual(resolve_script(root, ("tasks", "cleanup")), inferred.resolve())

            exact = root / "tool"
            exact.write_text("tool", encoding="utf-8")
            exact.chmod(exact.stat().st_mode | 0o111)
            self.assertEqual(resolve_script(root, ("tool",)), exact.resolve())

    def test_ambiguous_and_missing_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "task.py").write_text("", encoding="utf-8")
            (root / "task.sh").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ZushError, "task.py.*task.sh|task.sh.*task.py"):
                resolve_script(root, ("task",))
            with self.assertRaisesRegex(ZushError, "unknown script"):
                resolve_script(root, ("missing",))

    def test_runner_argv_matrix(self) -> None:
        found = {"pwsh": "/bin/pwsh", "sh": "/bin/sh", "cmd": "C:/cmd.exe"}
        which = found.get
        self.assertEqual(runner_argv(Path("tool.py"), ["x"], which), [sys.executable, "tool.py", "x"])
        self.assertEqual(runner_argv(Path("tool.ps1"), ["x"], which), ["/bin/pwsh", "-File", "tool.ps1", "x"])
        self.assertEqual(runner_argv(Path("tool.sh"), ["x"], which), ["/bin/sh", "tool.sh", "x"])
        self.assertEqual(
            runner_argv(Path("tool.cmd"), ["x"], which),
            ["C:/cmd.exe", "/d", "/s", "/c", "tool.cmd", "x"],
        )

    def test_missing_runner_is_rejected(self) -> None:
        with self.assertRaisesRegex(ZushError, "PowerShell"):
            runner_argv(Path("tool.ps1"), [], lambda _name: None)
