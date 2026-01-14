from __future__ import annotations

import pytest

from tprof import tprof
from tprof.api import _extract_code, _format_time


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
        assert len(errlines) == 3
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_called_once.<locals>.sample() "
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
        assert len(errlines) == 3
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_other_method.<locals>.sample() "
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
        assert len(errlines) == 3
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_raises.<locals>.sample() "
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
        assert len(errlines) == 3
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_recursive.<locals>.factorial() "
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
        assert len(errlines) == 3
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[2].startswith(
            " <unknown>:TestTprof.test_bad_dunder_module.<locals>.sample() "
        )

    def test_custom_label(self, capsys):
        def sample() -> int:
            return 42

        def main() -> None:
            sample()

        with tprof(sample, label="sample"):
            main()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 3
        assert errlines[0].startswith("🎯 tprof results @ sample:")
        assert errlines[1].startswith(" function")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_custom_label.<locals>.sample() "
        )

    def test_compare(self, capsys):
        def before() -> int:
            return 1

        def after() -> int:
            return 2

        with tprof(before, after, compare=True):
            before()
            after()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 4
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[1].rstrip().endswith(" delta")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_compare.<locals>.before() "
        )
        assert errlines[2].rstrip().endswith(" -")
        assert errlines[3].startswith(
            " tests.test_api:TestTprof.test_compare.<locals>.after() "
        )
        assert errlines[3].rstrip().endswith("%")

    def test_compare_no_baseline(self, capsys):
        def before() -> int:  # pragma: no cover
            return 1

        def after() -> int:
            return 2

        with tprof(before, after, compare=True):
            after()

        out, err = capsys.readouterr()
        assert out == ""
        errlines = err.splitlines()
        assert len(errlines) == 4
        assert errlines[0].startswith("🎯 tprof results:")
        assert errlines[1].startswith(" function")
        assert errlines[1].rstrip().endswith(" delta")
        assert errlines[2].startswith(
            " tests.test_api:TestTprof.test_compare_no_baseline.<locals>.before() "
        )
        assert errlines[2].rstrip().endswith(" -")
        assert errlines[3].startswith(
            " tests.test_api:TestTprof.test_compare_no_baseline.<locals>.after() "
        )
        assert errlines[3].rstrip().endswith(" n/a")


class TestFormatTime:
    def test_ns_no_colour(self):
        assert _format_time(999, None) == "999ns"

    def test_ns_with_colour(self):
        assert _format_time(999, "red") == "[red]999[/red]ns"

    def test_us_no_colour(self):
        assert _format_time(1_500, None) == "2μs"

    def test_us_with_colour(self):
        assert _format_time(1_500, "green") == "[green]2[/green]μs"

    def test_ms_no_colour(self):
        assert _format_time(2_500_000, None) == "2ms"

    def test_ms_with_colour(self):
        assert _format_time(2_500_000, "blue") == "[blue]2[/blue]ms"

    def test_s_no_colour(self):
        assert _format_time(3_500_000_000, None) == "4s "

    def test_s_with_colour(self):
        assert _format_time(3_500_000_000, "yellow") == "[yellow]4[/yellow]s "

    def test_big_s_no_colour(self):
        assert _format_time(12_345_678_901_234, None) == "12,346s "


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
