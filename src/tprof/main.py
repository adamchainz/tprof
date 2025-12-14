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
        "-m",
        metavar="module",
        dest="module",
        required=True,
        help="Run library module as a script (like python -m)",
    )

    if len(argv) == 0:
        # If no arguments were given, print the whole help message, rather
        # than fail with error about missing required arguments.
        parser.print_help()
        return 2

    args, unparsed_argv = parser.parse_known_args(argv)

    # TODO: script support
    # if args.module:

    # When profiling a module, consider the arguments after "-m module" to
    # be arguments to the module itself, so parse the arguments before
    # "-m" to check if any are invalid, for example:
    # "tprof -m foo --spam" means passing "--spam" to "foo"
    # "tprof --spam -m foo" means passing "--spam" to "tprof", which is invalid
    index = argv.index("-m") + 2
    parser.parse_args(argv[:index])

    # TODO: script support
    # if args.module and args.script:
    #     parser.error("Cannot specify both script and -m module")
    # if not args.module and not args.script:
    #     parser.error("Must specify either script or -m module")

    with tprof(*args.targets):
        # Run as module (like python -m)
        orig_sys_argv = sys.argv
        sys.argv = [args.module, *unparsed_argv]
        try:
            import runpy

            runpy.run_module(args.module, run_name="__main__", alter_sys=True)
        finally:
            sys.argv = orig_sys_argv

    return 0
