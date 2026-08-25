"""Small, reusable atomic-output helpers."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def staged_output_path(destination: str | Path) -> Iterator[Path]:
    """Yield a unique same-directory path and always remove an uncommitted file."""
    final_path = Path(destination).expanduser().resolve()
    final_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{final_path.stem}.tmp-",
        suffix=final_path.suffix,
        dir=final_path.parent,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    temporary.unlink(missing_ok=True)
    try:
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def commit_staged_output(staged: str | Path, destination: str | Path) -> Path:
    """Atomically replace destination with an already validated staged file."""
    staged_path = Path(staged).expanduser().resolve()
    final_path = Path(destination).expanduser().resolve()
    os.replace(staged_path, final_path)
    return final_path


__all__ = ["commit_staged_output", "staged_output_path"]
