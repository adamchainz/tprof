from __future__ import annotations

import subprocess
import sys
from textwrap import dedent

from tests.utils import tmp_importable
from tprof import __main__  # noqa: F401
from tprof.main import main


def test_main_no_arguments(capsys):
    """
    Main should fail without any arguments.
    """
    status_code = main([])

    assert status_code == 2
    out, err = capsys.readouterr()
    assert out.startswith("usage: tprof ")
    assert err == ""


def test_main_help_subprocess():
    proc = subprocess.run(
        [sys.executable, "-m", "tprof", "--help"],
        check=True,
        capture_output=True,
    )

    assert proc.stdout.startswith(b"usage: tprof ")


def test_main_module(tmp_path, capsys):
    path = tmp_path / "example.py"
    path.write_text(
        dedent(
            """\
            from pathlib import Path

            for _ in range(100):
                Path('.')

            print("Done.")
            """
        )
    )

    with tmp_importable(tmp_path, "example"):
        result = main(["-t", "pathlib:Path.__new__", "-m", "example"])

    assert result == 0
    out, err = capsys.readouterr()
    assert out == "Done.\n"
    errlines = err.splitlines()
    assert len(errlines) == 2
    assert errlines[0] == "🎯 tprof total times:"
    assert errlines[1].startswith("  pathlib:Path.__new__(): ")
