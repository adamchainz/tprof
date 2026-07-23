=========
Changelog
=========

* Reduce overhead by storing times in C data structures and disabling monitoring events for non-target code.
  Non-target functions no longer have any overhead, target functions have a 3x reduction in overhead, and memory use is 4x lower, and report calculation is ~100x faster.

  `PR #47 <https://github.com/adamchainz/tprof/pull/47>`__.

* Report the median rather than the mean, since it is more robust to outliers.
  Comparison mode deltas are now computed from medians too.

  `PR #48 <https://github.com/adamchainz/tprof/pull/48>`__.

* Fix timings for generators, coroutines, and asynchronous generators to exclude time spent suspended.

  `PR #49 <https://github.com/adamchainz/tprof/pull/49>`__.

* Build with frame pointers enabled, preparation for `PEP 831 <https://peps.python.org/pep-0831/>`__.

  `PR #40 <https://github.com/adamchainz/tprof/issues/40>`__.

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
