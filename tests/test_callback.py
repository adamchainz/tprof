# python
from __future__ import annotations

import time
from types import CodeType

from tprof import tprof

test_name = "test_callback"

expected_ns = 1e6
delay_sec = expected_ns / 1e9

expected_function_names = ["sample_a", "sample_b"]


def call_times_callback(
    label: str | None, call_times: dict[CodeType, list[int]]
) -> None:
    assert label == test_name
    function_names = []
    for code_type, times in call_times.items():
        assert len(times) == 1
        function_time = times[0]
        assert function_time >= 1e6  # in nanoseconds (we slept for 1 ms)
        function_names.append(code_type.co_name)
    assert sorted(function_names) == sorted(expected_function_names)


def sample_a() -> int:
    time.sleep(delay_sec)
    return 42


def sample_b() -> int:
    time.sleep(delay_sec)
    return 43


def main() -> None:
    sample_a()
    sample_b()


def test_callback() -> None:
    with tprof(
        sample_a, sample_b, label=test_name, call_times_callback=call_times_callback
    ):
        main()
