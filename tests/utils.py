from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def tmp_importable(path: Path, module_name: str) -> Generator[None]:
    """Add path to sys.path and clean up sys.modules afterwards."""
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path.remove(str(path))
        sys.modules.pop(module_name, None)
