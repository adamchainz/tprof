from __future__ import annotations

import pytest

from tprof import tprof
from tprof.api import Colourizer, _extract_code, _format_time


class TestTprof:
    def test_no_targets(self):
        with pytest.raises(ValueError) as excinfo, tprof():
            pass  # pragma: no cover

        assert str(excinfo.value) == "At least one target callable must be provided."

    def test_target_not_callable(self):
        thing = 1

        with pytest.raises(ValueError) as excinfo, tprof(thing):
            pass  # pragma: no cover

        assert str(excinfo.value) == "Cannot extract code object from 1."

    def test_called_once(self, capsys):
        def sample() -> int:
            return 42

        def main() -> None:
            sample()

        with tprof(sample):
            main()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 2
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(
            "  tests.test_api:TestTprof.test_called_once.<locals>.sample(): "
        )

    def test_other_method(self, capsys):
        def sample() -> int:
            return 42

        def other() -> None:
            sample()

        def main() -> None:
            other()

        with tprof(sample):
            main()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 2
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(
            "  tests.test_api:TestTprof.test_other_method.<locals>.sample(): "
        )

    def test_raises(self, capsys):
        def sample() -> None:
            raise RuntimeError("Failure")

        def main() -> None:
            try:
                sample()
            except RuntimeError:
                pass

        with tprof(sample):
            main()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 2
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(
            "  tests.test_api:TestTprof.test_raises.<locals>.sample(): "
        )

    def test_recursive(self, capsys):
        def factorial(n: int) -> int:
            if n == 0:
                return 1
            return n * factorial(n - 1)

        def main() -> None:
            factorial(5)

        with tprof(factorial):
            main()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 2
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(
            "  tests.test_api:TestTprof.test_recursive.<locals>.factorial(): "
        )

    def test_bad_dunder_module(self, capsys):
        def sample() -> int:
            return 42

        def main() -> None:
            sample()

        sample.__module__ = None  # type: ignore[assignment]

        with tprof(sample):
            main()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 2
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(
            "  <unknown>:TestTprof.test_bad_dunder_module.<locals>.sample(): "
        )


class TestColourizer:
    def test_bold_enabled(self):
        colourizer = Colourizer(enabled=True)
        result = colourizer.bold("Test")
        assert result == "\033[1mTest\033[0m"

    def test_bold_disabled(self):
        colourizer = Colourizer(enabled=False)
        result = colourizer.bold("Test")
        assert result == "Test"

    def test_red_bold_enabled(self):
        colourizer = Colourizer(enabled=True)
        result = colourizer.red_bold("Error")
        assert result == "\033[1;31mError\033[0m"

    def test_red_bold_disabled(self):
        colourizer = Colourizer(enabled=False)
        result = colourizer.red_bold("Error")
        assert result == "Error"


class TestFormatTime:
    def test_format_time_ns(self):
        assert _format_time(500) == "500ns"

    def test_format_time_us(self):
        assert _format_time(1500) == "2μs"
        assert _format_time(999_999) == "1,000μs"

    def test_format_time_ms(self):
        assert _format_time(1_500_000) == "2ms"
        assert _format_time(999_999_999) == "1,000ms"

    def test_format_time_s(self):
        assert _format_time(1_500_000_000) == "2s"
        assert _format_time(3_600_000_000_000) == "3,600s"


class TestExtractCode:
    def test_code_object(self):
        def jump():  # pragma: no cover
            pass

        code = _extract_code(jump.__code__)

        assert code is jump.__code__

    def test_function(self):
        def jump():  # pragma: no cover
            pass

        code = _extract_code(jump)

        assert code is jump.__code__

    def test_method(self):
        class Robot:
            def jump(self):  # pragma: no cover
                pass

        code = _extract_code(Robot.jump)

        assert code is Robot.jump.__code__

    def test_method_instance(self):
        class Robot:
            def jump(self):  # pragma: no cover
                pass

        obj = Robot()
        code = _extract_code(obj.jump)

        assert code is obj.jump.__code__

    def test_static_method(self):
        class Robot:
            @staticmethod
            def jump():  # pragma: no cover
                pass

        code = _extract_code(Robot.jump)

        assert code is Robot.jump.__code__

    def test_static_method_instance(self):
        class Robot:
            @staticmethod
            def jump():  # pragma: no cover
                pass

        obj = Robot()
        code = _extract_code(obj.jump)

        assert code is obj.jump.__code__

    def test_class_method(self):
        class Robot:
            @classmethod
            def jump(cls):  # pragma: no cover
                pass

        code = _extract_code(Robot.jump)

        assert code is Robot.jump.__code__

    def test_class_method_instance(self):
        class Robot:
            @classmethod
            def jump(cls):  # pragma: no cover
                pass

        obj = Robot()
        code = _extract_code(obj.jump)

        assert code is obj.jump.__code__

    def test_callable_instance(self):
        class Robot:
            def __call__(self):  # pragma: no cover
                pass

        obj = Robot()
        code = _extract_code(obj)

        assert code is obj.__call__.__code__

    def test_callable_bad_call(self):
        class Robot:
            __call__ = 42

        obj = Robot()

        code = _extract_code(obj)

        assert code is None

    def test_string(self):
        code = _extract_code(f"{__name__}.sample")

        assert code is sample.__code__


def sample():  # pragma: no cover
    pass
