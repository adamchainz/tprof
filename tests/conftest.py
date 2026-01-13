from __future__ import annotations

import os
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def set_columns():
    """
    Set COLUMNS to fixed value for consistent Rich output.
    """
    with mock.patch.dict(os.environ, {"COLUMNS": "120"}):
        yield
