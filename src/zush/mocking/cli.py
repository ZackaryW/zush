from __future__ import annotations

from pathlib import Path


def parse_mock_path(argv: list[str]) -> tuple[Path | None, list[str]]:
    out: list[str] = []
    mock_path: Path | None = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("--mock-path", "-m"):
            if index + 1 < len(argv):
                mock_path = Path(argv[index + 1])
                index += 2
                continue
        out.append(arg)
        index += 1
    return mock_path, out
