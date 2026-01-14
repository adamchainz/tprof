from __future__ import annotations

import subprocess
import sys
from contextlib import chdir
from pathlib import Path
from textwrap import dedent
from unittest import mock

from rich.console import Console

from tprof import __main__  # noqa: F401
from tprof import api as tprof_api
from tprof.main import main


def test_generate_screenshot(tmp_path):
    """
    Generates a screenshot.

    Delete the existing screenshot.svg to regenerate.
    """
    path = tmp_path / "example.py"
    path.write_text(
        dedent(
            """\
            from pathlib import Path

            for _ in range(1_000):
                Path('.').exists()

            print("Done.")
            """
        )
    )
    console = Console(record=True, width=80)
    args = ["-t", "pathlib:Path.__new__", "example.py"]
    console.print(f"$ tprof {' '.join(args)}\n")
    with mock.patch.object(tprof_api, "console", console), chdir(tmp_path):
        main(args)

    svg = console.export_svg(title="")
    svg_path = Path(__file__).parent.parent / "screenshot.svg"
    if not svg_path.exists():  # pragma: no cover
        svg_path.write_text(svg)


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
    assert len(errlines) == 3
    assert errlines[0] == "🎯 tprof results:"
    assert errlines[1].startswith(" function")
    assert errlines[2].startswith(" pathlib:Path.__new__() ")


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
        with chdir(tmp_path):
            result = main(["-t", "pathlib:Path.__new__", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0
    out, err = capsys.readouterr()
    assert out == "Done.\n"
    errlines = err.splitlines()
    assert len(errlines) == 3
    assert errlines[0] == "🎯 tprof results:"
    assert errlines[1].startswith(" function")
    assert errlines[2].startswith(" pathlib:Path.__new__() ")


def test_main_compare(tmp_path, capsys):
    path = tmp_path / "example.py"
    path.write_text(
        dedent(
            """\
            def before():
                pass

            def after():
                pass

            for _ in range(100):
                before()
                after()
            """
        )
    )

    try:
        with chdir(tmp_path):
            result = main(["-x", "-t", "before", "-t", "after", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0
    out, err = capsys.readouterr()
    assert out == ""
    errlines = err.splitlines()
    assert len(errlines) == 4
    assert errlines[0] == "🎯 tprof results:"
    assert errlines[1].startswith(" function")
    assert errlines[1].rstrip().endswith(" delta")
    assert errlines[2].startswith(" example:before() ")
    assert errlines[2].rstrip().endswith(" -")
    assert errlines[3].startswith(" example:after() ")
    assert errlines[3].rstrip().endswith("%")
