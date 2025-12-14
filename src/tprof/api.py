from __future__ import annotations

import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pkgutil import resolve_name
from types import CodeType
from typing import Any

TOOL_ID = sys.monitoring.PROFILER_ID
TOOL_NAME = "tprof"


@contextmanager
def tprof(*targets: Any) -> Generator[None]:
    """
    Profile time spent in target callables and print a report when done.
    """
    code_to_name: dict[CodeType, str] = {}
    enter_times: dict[CodeType, list[int]] = {}
    total_times: dict[str, int] = {}

    if not targets:
        raise ValueError("At least one target callable must be provided.")

    for target in targets:
        code = _extract_code(target)
        if code is None:
            raise ValueError(f"Cannot extract code object from {target}")

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
        total_times[name] = 0

    def py_start_callback(code: CodeType, instruction_offset: int) -> object:
        if code in enter_times:
            enter_times[code].append(time.perf_counter_ns())
        return None

    def py_return_callback(
        code: CodeType, instruction_offset: int, retval: object
    ) -> object:
        if code in enter_times and enter_times[code]:
            enter_time = enter_times[code].pop()
            elapsed = time.perf_counter_ns() - enter_time
            name = code_to_name[code]
            total_times[name] += elapsed
        return None

    def py_unwind_callback(
        code: CodeType, instruction_offset: int, exception: BaseException
    ) -> object:
        if code in enter_times and enter_times[code]:
            enter_time = enter_times[code].pop()
            elapsed = time.perf_counter_ns() - enter_time
            name = code_to_name[code]
            total_times[name] += elapsed
        return None

    sys.monitoring.use_tool_id(TOOL_ID, TOOL_NAME)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_START, py_start_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_RETURN, py_return_callback
    )
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_UNWIND, py_unwind_callback
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

        c = Colourizer(sys.stderr)
        print(f"🎯 {c.red_bold('tprof')} total times:", file=sys.stderr)
        for name in total_times:
            for name in sorted(total_times):
                formatted_time = _format_time(total_times[name])
                print(f"  {c.bold(name + '()')}: {formatted_time}", file=sys.stderr)


class Colourizer:
    __slots__ = ("enabled",)

    def __init__(self, stream: Any) -> None:
        self.enabled = stream.isatty()

    def bold(self, text: str) -> str:
        if self.enabled:
            return f"\033[1m{text}\033[0m"
        return text

    def red_bold(self, text: str) -> str:
        if self.enabled:
            return f"\033[1;31m{text}\033[0m"
        return text


def _format_time(ns: int) -> str:
    """Format time in nanoseconds to appropriate scale with comma separators."""
    if ns < 1_000:
        return f"{ns}ns"
    elif ns < 1_000_000:
        us = ns / 1_000
        return f"{us:.0f}μs"
    elif ns < 1_000_000_000:
        ms = ns / 1_000_000
        return f"{ms:.0f}ms"
    else:
        s = ns / 1_000_000_000
        return f"{s:,.0f}s"


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

    try:
        code = obj.__func__.__code__
        return code
    except AttributeError:
        pass

    if callable(obj) and hasattr(obj, "__call__"):  # noqa: B004
        call_method = obj.__call__
        try:
            code = call_method.__func__.__code__
            return code
        except AttributeError:
            pass
        try:
            code = call_method.__code__
            return code
        except AttributeError:
            pass

    return None
