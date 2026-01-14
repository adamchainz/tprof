from __future__ import annotations

import sys

from setuptools import Extension, setup

if hasattr(sys, "pypy_version_info"):
    raise RuntimeError("tprof does not currently support PyPy.")


setup(
    ext_modules=[
        Extension(name="tprof.record", sources=["src/tprof/record.c"]),
    ],
)
