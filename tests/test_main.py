from __future__ import annotations

import subprocess
import sys
from contextlib import chdir
from textwrap import dedent
from unittest import mock

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


def test_main_no_arguments_sys_argv(capsys):
    """
    Main should fail without any arguments.
    """
    with mock.patch.object(sys, "argv", ["tprof"]):
        status_code = main()

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


def test_main_script(tmp_path, capsys):
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

    with chdir(tmp_path):
        result = main(["-t", "pathlib:Path.__new__", "example.py"])

    assert result == 0
    out, err = capsys.readouterr()
    assert out == "Done.\n"
    errlines = err.splitlines()
    assert len(errlines) == 2
    assert errlines[0] == "🎯 tprof total times:"
    assert errlines[1].startswith("  pathlib:Path.__new__(): ")


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

    try:
        with chdir(tmp_path), mock.patch.object(sys, "path", [str(tmp_path)]):
            result = main(["-t", "pathlib:Path.__new__", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0
    out, err = capsys.readouterr()
    assert out == "Done.\n"
    errlines = err.splitlines()
    assert len(errlines) == 2
    assert errlines[0] == "🎯 tprof total times:"
    assert errlines[1].startswith("  pathlib:Path.__new__(): ")
