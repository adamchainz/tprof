from __future__ import annotations

import json
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pkgutil import resolve_name
from types import CodeType
from typing import Any

from rich.console import Console
from rich.table import Table

TOOL_ID = sys.monitoring.PROFILER_ID
TOOL_NAME = "tprof"

console = Console(stderr=True)

code_to_name: dict[CodeType, str] = {}


@dataclass
class FunctionStats:
    name: str
    calls: int
    total_ns: int
    min_ns: int
    max_ns: int
    median_ns: float
    stdev_ns: float


@contextmanager
def tprof(
    *targets: Any,
    label: str | None = None,
    compare: bool = False,
    json_path: str | None = None,
    baseline_path: str | None = None,
) -> Generator[list[FunctionStats]]:
    """
    Profile time spent in target callables and print a report when done.
    """

    from tprof import record

    if not targets:
        raise ValueError("At least one target callable must be provided.")
    if compare and baseline_path is not None:
        raise ValueError("compare and baseline_path may not be combined.")

    baseline = None
    if baseline_path is not None:
        baseline = _load_baseline(baseline_path)

    names: dict[CodeType, str] = {}
    for target in targets:
        code = _extract_code(target)
        if code is None:
            raise ValueError(f"Cannot extract code object from {target!r}.")

        if isinstance(target, str):
            name = target
        else:
            base_name = (
                getattr(target, "__qualname__", None)
                or getattr(target, "__name__", None)
                or repr(target)
            )

            module = getattr(target, "__module__", None)
            if module:
                name = f"{module}:{base_name}"
            else:
                name = f"<unknown>:{base_name}"

        names[code] = name

    code_to_name.clear()
    code_to_name.update(names)
    record.configure(tuple(names))

    sys.monitoring.use_tool_id(TOOL_ID, TOOL_NAME)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_START, record.py_start_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_RESUME, record.py_resume_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_THROW, record.py_throw_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_YIELD, record.py_yield_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_RETURN, record.py_return_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_UNWIND, record.py_unwind_callback
    )

    sys.monitoring.set_events(
        TOOL_ID,
        (
            sys.monitoring.events.PY_START
            | sys.monitoring.events.PY_RESUME
            | sys.monitoring.events.PY_THROW
            | sys.monitoring.events.PY_YIELD
            | sys.monitoring.events.PY_RETURN
            | sys.monitoring.events.PY_UNWIND
        ),
    )
    # Re-enable events at code locations that callbacks disabled with
    # sys.monitoring.DISABLE during any previous profiling session.
    sys.monitoring.restart_events()

    results: list[FunctionStats] = []
    exc = False
    try:
        yield results
    except Exception:
        exc = True
        raise
    finally:
        sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_RESUME, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_THROW, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_YIELD, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_RETURN, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_UNWIND, None)
        sys.monitoring.free_tool_id(TOOL_ID)

        results[:] = [
            FunctionStats(name, count, total, min_ns, max_ns, median_ns, stdev_ns)
            for name, (count, total, min_ns, max_ns, median_ns, stdev_ns) in zip(
                code_to_name.values(), record.stats(), strict=True
            )
        ]

        if not exc:
            if json_path is not None:
                _write_json(json_path, label, results)
            display_report(results, label=label, compare=compare, baseline=baseline)

        code_to_name.clear()
        record.configure(())


def _load_baseline(path: str) -> dict[str, float]:
    try:
        with open(path) as fp:
            data = json.load(fp)
        return {
            function["name"]: function["median_ns"] for function in data["functions"]
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"Cannot load baseline from {path!r}: {exc}") from exc


def _write_json(path: str, label: str | None, results: list[FunctionStats]) -> None:
    data = {
        "version": 1,
        "label": label,
        "functions": [asdict(function_stats) for function_stats in results],
    }
    if path == "-":
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        with open(path, "w") as fp:
            json.dump(data, fp, indent=2)
            fp.write("\n")


def display_report(
    results: list[FunctionStats],
    label: str | None = None,
    compare: bool = False,
    baseline: dict[str, float] | None = None,
) -> None:
    heading = "[bold red]🎯 tprof[/bold red] results"
    if label:
        heading += f" @ [bold bright_blue]{label}[/bold bright_blue]"
    heading += ":"
    console.print(heading)

    table = Table(box=None, collapse_padding=True)

    table.add_column("function")
    table.add_column("calls", justify="right")
    table.add_column("total", justify="right")
    table.add_column("median", header_style="bright_green", justify="right")
    table.add_column("±", justify="right")
    table.add_column("σ", header_style="bright_green", justify="left")
    table.add_column("min", header_style="cyan", justify="right")
    table.add_column("…", justify="right")
    table.add_column("max", header_style="magenta", justify="left")
    if compare or baseline is not None:
        table.add_column("delta")

    compare_baseline: float | None = None
    first = True

    for function_stats in results:
        count = function_stats.calls
        median_ns = function_stats.median_ns

        delta: tuple[str, ...] = ()
        if compare:
            if first:
                delta = ("[dim]-[/dim]",)
                if count:
                    compare_baseline = median_ns
            else:
                if not compare_baseline:
                    delta = ("[dim]n/a[/dim]",)
                else:
                    delta = (_format_delta(median_ns, compare_baseline),)
        elif baseline is not None:
            baseline_median = baseline.get(function_stats.name)
            if count and baseline_median:
                delta = (_format_delta(median_ns, baseline_median),)
            else:
                delta = ("[dim]n/a[/dim]",)

        first = False
        table.add_row(
            f"[bold]{function_stats.name}()[/bold]",
            str(count),
            _format_time(function_stats.total_ns, None),
            (
                _format_time(int(median_ns), "bright_green")
                if count
                else "[dim]n/a[/dim]"
            ),
            "±" if count > 1 else "",
            (
                _format_time(int(function_stats.stdev_ns), "bright_green")
                if count > 1
                else ""
            ),
            _format_time(function_stats.min_ns, "cyan") if count else "[dim]n/a[/dim]",
            "…",
            _format_time(function_stats.max_ns, "magenta")
            if count
            else "[dim]n/a[/dim]",
            *delta,
        )
    console.print(table)


def _format_delta(median_ns: float, baseline_ns: float) -> str:
    percent_diff = ((median_ns - baseline_ns) / baseline_ns) * 100
    colour = "bold bright_green" if percent_diff <= 0 else "bold bright_red"
    return f"[{colour}]{percent_diff:+.2f}%[/{colour}]"


def _format_time(ns: int, colour: str | None) -> str:
    """Format time in nanoseconds to appropriate scale with at least 3 significant digits."""
    if ns < 1_000:
        value = str(ns)
        suffix = "ns"
    elif ns < 1_000_000:
        us = ns / 1_000
        if us < 10:
            value = f"{us:.2f}"
        elif us < 100:
            value = f"{us:.1f}"
        else:
            value = f"{us:.0f}"
        suffix = "μs"
    elif ns < 1_000_000_000:
        ms = ns / 1_000_000
        if ms < 10:
            value = f"{ms:.2f}"
        elif ms < 100:
            value = f"{ms:.1f}"
        else:
            value = f"{ms:,.0f}"
        suffix = "ms"
    else:
        s = ns / 1_000_000_000
        if s < 10:
            value = f"{s:.2f}"
        elif s < 100:
            value = f"{s:.1f}"
        else:
            value = f"{s:,.0f}"
        suffix = "s "

    if colour:
        return f"[{colour}]{value}[/{colour}]{suffix}"
    else:
        return f"{value}{suffix}"


def _extract_code(obj: Any) -> CodeType | None:
    """Extract code object from various callable types."""
    if isinstance(obj, str):
        obj = resolve_name(obj)

    if isinstance(obj, CodeType):
        return obj

    code: CodeType

    try:
        code = obj.__code__
        return code
    except AttributeError:
        pass

    if callable(obj) and hasattr(obj, "__call__"):  # noqa: B004
        call_method = obj.__call__
        try:
            code = call_method.__code__
            return code
        except AttributeError:
            pass

    return None
