from __future__ import annotations

import sys

from setuptools import Extension, setup

if hasattr(sys, "pypy_version_info"):
    raise RuntimeError("tprof does not currently support PyPy.")

extra_compile_args = []
libraries = []
if sys.platform != "win32":
    extra_compile_args += [
        "-fno-omit-frame-pointer",
        "-mno-omit-leaf-frame-pointer",
    ]
    # for sqrt()
    libraries.append("m")

setup(
    ext_modules=[
        Extension(
            name="tprof.record",
            sources=["src/tprof/record.c"],
            extra_compile_args=extra_compile_args,
            libraries=libraries,
        ),
    ],
)
