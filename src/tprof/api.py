from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from pkgutil import resolve_name
from statistics import mean, stdev
from types import CodeType
from typing import Any

from rich.console import Console
from rich.table import Table

TOOL_ID = sys.monitoring.PROFILER_ID
TOOL_NAME = "tprof"

console = Console(stderr=True)

code_to_name: dict[CodeType, str] = {}
enter_times: dict[CodeType, list[int]] = {}
call_times: dict[CodeType, list[int]] = {}


@contextmanager
def tprof(
    *targets: Any,
    label: str | None = None,
    compare: bool = False,
) -> Generator[None]:
    """
    Profile time spent in target callables and print a report when done.
    """

    from tprof import record

    if not targets:
        raise ValueError("At least one target callable must be provided.")

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

        code_to_name[code] = name
        enter_times[code] = []
        call_times[code] = []

    sys.monitoring.use_tool_id(TOOL_ID, TOOL_NAME)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_START, record.py_start_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_RETURN, record.py_end_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_UNWIND, record.py_end_callback
    )

    sys.monitoring.set_events(
        TOOL_ID,
        (
            sys.monitoring.events.PY_START
            | sys.monitoring.events.PY_RETURN
            | sys.monitoring.events.PY_UNWIND
        ),
    )

    try:
        yield
    finally:
        sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_RETURN, None)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_UNWIND, None)
        sys.monitoring.free_tool_id(TOOL_ID)

        heading = "[bold red]🎯 tprof[/bold red] results"
        if label:
            heading += f" @ [bold bright_blue]{label}[/bold bright_blue]"
        heading += ":"
        console.print(heading)

        table = Table(box=None, collapse_padding=True)

        table.add_column("function")
        table.add_column("calls", justify="right")
        table.add_column("total", justify="right")
        table.add_column("mean", header_style="bright_green", justify="right")
        table.add_column("±", justify="right")
        table.add_column("σ", header_style="bright_green", justify="left")
        table.add_column("min", header_style="cyan", justify="right")
        table.add_column("…", justify="right")
        table.add_column("max", header_style="magenta", justify="left")
        if compare:
            table.add_column("delta")

        baseline: float | None = None
        first = True

        for code, times in call_times.items():
            mean_times = mean(times) if times else 0.0

            if not compare:
                delta: tuple[str, ...] = ()
            else:
                if first:
                    delta = ("[dim]-[/dim]",)
                    if times:
                        baseline = mean_times
                else:
                    if not baseline:
                        delta = ("[dim]n/a[/dim]",)
                    else:
                        percent_diff = ((mean_times - baseline) / baseline) * 100
                        colour = (
                            "bold bright_green"
                            if percent_diff <= 0
                            else "bold bright_red"
                        )
                        delta = (f"[{colour}]{percent_diff:+.2f}%[/{colour}]",)

            first = False
            table.add_row(
                f"[bold]{code_to_name[code]}()[/bold]",
                str(len(times)),
                _format_time(sum(times), None),
                (
                    _format_time(int(mean_times), "bright_green")
                    if times
                    else "[dim]n/a[/dim]"
                ),
                "±" if len(times) > 1 else "",
                _format_time(int(stdev(times)), "bright_green")
                if len(times) > 1
                else "",
                _format_time(min(times), "cyan") if times else "[dim]n/a[/dim]",
                "…",
                _format_time(max(times), "magenta") if times else "[dim]n/a[/dim]",
                *delta,
            )
        console.print(table)

        code_to_name.clear()
        enter_times.clear()
        call_times.clear()


def _format_time(ns: int, colour: str | None) -> str:
    """Format time in nanoseconds to appropriate scale with comma separators."""
    if ns < 1_000:
        value = str(ns)
        suffix = "ns"
    elif ns < 1_000_000:
        value = f"{ns / 1_000:.0f}"
        suffix = "μs"
    elif ns < 1_000_000_000:
        value = f"{ns / 1_000_000:.0f}"
        suffix = "ms"
    else:
        value = f"{ns / 1_000_000_000:,.0f}"
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
