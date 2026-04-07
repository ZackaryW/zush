from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from zush.core.storage import DirectoryStorage


@contextmanager
def temporary_storage(prefix: str = "zush-"):
    """Yield a DirectoryStorage backed by a temporary directory and clean it up on exit."""
    with TemporaryDirectory(prefix=prefix) as temp_dir:
        yield DirectoryStorage(Path(temp_dir))
