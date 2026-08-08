=========
Changelog
=========

1.3.0 (2026-08-08)
------------------

* Reduce overhead by storing times in C data structures and disabling monitoring events for non-target code.
  Non-target functions no longer have any overhead, target functions have a 3x reduction in overhead, and memory use is 4x lower, and report calculation is ~100x faster.

  `PR #47 <https://github.com/adamchainz/tprof/pull/47>`__.

* Report the median rather than the mean, since it is more robust to outliers.
  Comparison mode deltas are now computed from medians too.

  `PR #48 <https://github.com/adamchainz/tprof/pull/48>`__.

* ``tprof()`` now yields a list of ``FunctionStats`` objects, populated when the profiled block ends, for programmatic access to the results.

  `PR #52 <https://github.com/adamchainz/tprof/pull/52>`__.

* Add two options useful for comparing data between runs, such as when switching Git branches:

  * `--json <path>` (`json_path` in the API) writes the statistics to a file
    as JSON, or to stdout with '-'.

  * `--baseline <path>` (`baseline_path` in the API) reads a previous run's
    `--json` output and shows a delta column comparing each function's
    median against that run. Mutually exclusive with `-x` (`--compare`), which
    compares between targets within one run.

  `PR #53 <https://github.com/adamchainz/tprof/pull/53>`__.

* Build with frame pointers enabled, preparation for `PEP 831 <https://peps.python.org/pep-0831/>`__.

  `PR #40 <https://github.com/adamchainz/tprof/issues/40>`__.

* Stop shipping wheels for free-threaded Python 3.13 since `cibuildwheel 4.0.0 dropped support for building them <https://iscinumpy.dev/post/cibuildwheel-4-0-0/>__.

1.2.0 (2026-02-20)
------------------

* Format time output to at least three significant digits.

  `PR #28 <https://github.com/adamchainz/tprof/issues/28>`__.

1.1.0 (2026-01-26)
------------------

* Skip reporting statistics when an exception occurs.

  `Issue #15 <https://github.com/adamchainz/tprof/issues/15>`__.

* Record correct statistics for functions run concurrently in threads.

  `PR #21 <https://github.com/adamchainz/tprof/pull/21>`__.

* Stop shipping wheels for 32-bit Linux and Windows.

  `PR #18 <https://github.com/adamchainz/tprof/pull/18>`__.

1.0.0 (2026-01-14)
------------------

* Initial release.
