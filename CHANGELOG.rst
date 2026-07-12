=========
Changelog
=========

* Reduce profiling overhead by storing start and elapsed times in C data
  structures rather than Python dicts, lists, and ints, computing report
  statistics in C, and disabling monitoring events for non-target code.
  Approximately: recording overhead dropped threefold, to ~140ns per profiled
  call on Python 3.13, non-target function calls are no longer slowed at all
  (previously ~400ns each), memory use dropped fourfold, to 8 bytes per
  recorded call, and report calculation dropped from ~430ms to ~3ms per
  million recorded calls.

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
