from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence

from tprof.api import _load_baseline, tprof


def _parse_duration(value: str) -> int:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ns|us|μs|ms|s)", value)
    if match is None:
        raise argparse.ArgumentTypeError(
            f"invalid duration {value!r}, expected a number with a unit of "
            + "ns/us/ms/s, like '5ms'"
        )
    multiplier = {
        "ns": 1,
        "us": 1_000,
        "μs": 1_000,
        "ms": 1_000_000,
        "s": 1_000_000_000,
    }[match[2]]
    return int(float(match[1]) * multiplier)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="tprof", allow_abbrev=False)
    parser.suggest_on_error = True
    parser.add_argument(
        "-t",
        metavar="target",
        action="append",
        dest="targets",
        required=True,
        help="Target callable to profile (format: module:function).",
    )
    delta_group = parser.add_mutually_exclusive_group()
    delta_group.add_argument(
        "-x",
        "--compare",
        action="store_true",
        help="Compare performance of targets, with the first as baseline.",
    )
    delta_group.add_argument(
        "--baseline",
        dest="baseline_path",
        metavar="path",
        help="Compare against statistics from a previous run's --json file.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        metavar="path",
        help="Write statistics as JSON to this file, or '-' for stdout.",
    )
    parser.add_argument(
        "--fail-above",
        dest="fail_above",
        metavar="duration",
        type=_parse_duration,
        help=(
            "Exit with status 1 if any target's median time exceeds this "
            + "duration, e.g. '5ms'."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-m",
        metavar="module",
        dest="module",
        help="Run library module as a script (like python -m)",
    )
    group.add_argument("script", nargs="?", help="Python script to run")
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the script or module",
    )

    if len(argv) == 0:
        # If no arguments were given, print the whole help message, rather
        # than fail with error about missing required arguments.
        parser.print_help()
        return 2

    args = parser.parse_args(argv)

    if args.module:
        sys.path.insert(0, "")

    targets = args.targets
    if args.module:
        targets = [
            f"{args.module}:{target}" if ":" not in target else target
            for target in targets
        ]

    if args.baseline_path is not None:
        try:
            _load_baseline(args.baseline_path)
        except ValueError as exc:
            print(f"tprof: {exc}", file=sys.stderr)
            return 2

    with tprof(
        *targets,
        compare=args.compare,
        json_path=args.json_path,
        baseline_path=args.baseline_path,
    ) as results:
        orig_sys_argv = sys.argv
        sys.argv = [args.module, *args.args]
        try:
            if args.module:
                import runpy

                runpy.run_module(args.module, run_name="__main__", alter_sys=True)
            else:
                with open(args.script, "rb") as f:
                    code = compile(f.read(), args.script, "exec")
                    exec(
                        code,
                        {
                            "__name__": "__main__",
                            "__file__": args.script,
                        },
                    )
        finally:
            sys.argv = orig_sys_argv

    if args.module:
        sys.path.pop(0)

    if args.fail_above is not None:
        failed = False
        for function_stats in results:
            if function_stats.calls and function_stats.median_ns > args.fail_above:
                print(
                    f"tprof: {function_stats.name}() median "
                    + f"{int(function_stats.median_ns)}ns exceeds "
                    + f"{args.fail_above}ns",
                    file=sys.stderr,
                )
                failed = True
        if failed:
            return 1

    return 0
