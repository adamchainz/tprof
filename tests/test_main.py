from __future__ import annotations

import argparse
import json
import subprocess
import sys
from contextlib import chdir
from pathlib import Path
from textwrap import dedent
from unittest import mock

import pytest
from rich.console import Console

from tprof import __main__  # noqa: F401
from tprof import api as tprof_api
from tprof.main import _parse_duration, main


class TestParseDuration:
    def test_ns(self):
        assert _parse_duration("5ns") == 5

    def test_us(self):
        assert _parse_duration("1.5us") == 1_500

    def test_us_mu(self):
        assert _parse_duration("2μs") == 2_000

    def test_ms(self):
        assert _parse_duration("5ms") == 5_000_000

    def test_s(self):
        assert _parse_duration("1.5s") == 1_500_000_000

    def test_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError) as excinfo:
            _parse_duration("5parsecs")

        assert str(excinfo.value).startswith("invalid duration '5parsecs'")


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


SLEEPY_SCRIPT = dedent(
    """\
    import time

    def snooze():
        time.sleep(0.001)

    for _ in range(5):
        snooze()
    """
)


def test_main_json(tmp_path, capsys):
    (tmp_path / "example.py").write_text(SLEEPY_SCRIPT)
    json_path = tmp_path / "tprof.json"

    try:
        with chdir(tmp_path):
            result = main(["-t", "snooze", "--json", str(json_path), "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0
    data = json.loads(json_path.read_text())
    assert data["version"] == 1
    assert data["label"] is None
    (function_data,) = data["functions"]
    assert function_data["name"] == "example:snooze"
    assert function_data["calls"] == 5
    assert function_data["median_ns"] >= 1_000_000


def test_main_json_stdout(tmp_path, capsys):
    (tmp_path / "example.py").write_text(SLEEPY_SCRIPT)

    try:
        with chdir(tmp_path):
            result = main(["-t", "snooze", "--json", "-", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0
    out, err = capsys.readouterr()
    data = json.loads(out)
    assert data["version"] == 1


def test_main_baseline(tmp_path, capsys):
    (tmp_path / "example.py").write_text(SLEEPY_SCRIPT)
    json_path = tmp_path / "tprof.json"

    try:
        with chdir(tmp_path):
            result = main(["-t", "snooze", "--json", str(json_path), "-m", "example"])
            assert result == 0
            result = main(
                ["-t", "snooze", "--baseline", str(json_path), "-m", "example"]
            )
    finally:
        sys.modules.pop("example", None)

    assert result == 0
    out, err = capsys.readouterr()
    errlines = err.splitlines()
    assert len(errlines) == 6
    assert errlines[4].rstrip().endswith(" delta")
    assert errlines[5].startswith(" example:snooze() ")
    assert errlines[5].rstrip().endswith("%")


def test_main_baseline_invalid(tmp_path, capsys):
    (tmp_path / "example.py").write_text(SLEEPY_SCRIPT)
    json_path = tmp_path / "tprof.json"
    json_path.write_text("[]")

    with chdir(tmp_path):
        result = main(["-t", "snooze", "--baseline", str(json_path), "-m", "example"])

    assert result == 2
    out, err = capsys.readouterr()
    assert err.startswith("tprof: Cannot load baseline from ")


def test_main_baseline_and_compare(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["-t", "example:snooze", "-x", "--baseline", "tprof.json", "example.py"])

    assert excinfo.value.code == 2
    out, err = capsys.readouterr()
    assert "not allowed with argument" in err


def test_main_fail_above_exceeded(tmp_path, capsys):
    (tmp_path / "example.py").write_text(SLEEPY_SCRIPT)

    try:
        with chdir(tmp_path):
            result = main(["-t", "snooze", "--fail-above", "1ns", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 1
    out, err = capsys.readouterr()
    errlines = err.splitlines()
    assert errlines[-1].startswith("tprof: example:snooze() median ")
    assert errlines[-1].endswith("ns exceeds 1ns")


def test_main_fail_above_ok(tmp_path, capsys):
    (tmp_path / "example.py").write_text(SLEEPY_SCRIPT)

    try:
        with chdir(tmp_path):
            result = main(["-t", "snooze", "--fail-above", "10s", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0


def test_main_fail_above_uncalled(tmp_path, capsys):
    (tmp_path / "example.py").write_text(
        dedent(
            """\
            def snooze():
                pass
            """
        )
    )

    try:
        with chdir(tmp_path):
            result = main(["-t", "snooze", "--fail-above", "1ns", "-m", "example"])
    finally:
        sys.modules.pop("example", None)

    assert result == 0


def test_main_fail_above_invalid(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["-t", "example:snooze", "--fail-above", "5parsecs", "example.py"])

    assert excinfo.value.code == 2
    out, err = capsys.readouterr()
    assert "invalid duration '5parsecs'" in err
