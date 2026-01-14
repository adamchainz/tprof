from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tprof.api import tprof


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="tprof", allow_abbrev=False)
    parser.suggest_on_error = True  # type: ignore[attr-defined]
    parser.add_argument(
        "-t",
        metavar="target",
        action="append",
        dest="targets",
        required=True,
        help="Target callable to profile (format: module:function).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare performance of targets, with the first as baseline.",
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

    with tprof(*targets, compare=args.compare):
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

    return 0
