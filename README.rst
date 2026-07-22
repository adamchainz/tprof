=========
🎯 tprof
=========

.. image:: https://img.shields.io/github/actions/workflow/status/adamchainz/tprof/main.yml.svg?branch=main&style=for-the-badge
   :target: https://github.com/adamchainz/tprof/actions?workflow=CI

.. image:: https://img.shields.io/badge/Coverage-100%25-success?style=for-the-badge
   :target: https://github.com/adamchainz/tprof/actions?workflow=CI

.. image:: https://img.shields.io/pypi/v/tprof.svg?style=for-the-badge
   :target: https://pypi.org/project/tprof/

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
   :target: https://github.com/psf/black

.. image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=for-the-badge
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit

----

A targeting profiler.

.. figure:: https://raw.githubusercontent.com/adamchainz/tprof/main/screenshot.svg
   :alt: tprof in action.

----

**Get better at command line Git** with my book `Boost Your Git DX <https://adamchainz.gumroad.com/l/bygdx>`__.

----

Requirements
------------

Python 3.12 to 3.14 supported.

Installation
------------

1. Install with **pip**:

   .. code-block:: sh

       python -m pip install tprof

Usage
-----

tprof measures the time spent in specified target functions when running a script or module.
Unlike a full program profiler, it only tracks the specified functions using |sys.monitoring|__ (new in Python 3.12), reducing overhead and helping you focus on the bits you’re changing.
Timing is done in C to further reduce overhead.

.. |sys.monitoring| replace:: ``sys.monitoring``
__ https://docs.python.org/3/library/sys.html#sys.monitoring

tprof supports usage as a CLI and with a Python API.

CLI
---

Specify one or more target functions with ``-t``, then what to run: a script file by filename, or a module with ``-m`` then its name.
Any unrecognized arguments are passed to the script or module.

Use the format ``<module>:<function>`` to specify target functions.
When using ``-m`` with a module, you can skip the ``<module>`` part and it will be inferred from the module name.

.. code-block:: console

    $ tprof -t lib:maths ./example.py
    ...
    🎯 tprof results:
     function    calls total  median ± σ     min … max
     lib:maths()     2 610ms 305ms ± 2ms 304ms … 307ms

Full help:

.. [[[cog
.. import cog
.. import subprocess
.. import sys
.. result = subprocess.run(
..     [sys.executable, "-m", "tprof", "--help"],
..     capture_output=True,
..     text=True,
.. )
.. cog.outl("")
.. cog.outl(".. code-block:: console")
.. cog.outl("")
.. for line in result.stdout.splitlines():
..     if line.strip() == "":
..         cog.outl("")
..     else:
..         cog.outl("   " + line.rstrip())
.. cog.outl("")
.. ]]]

.. code-block:: console

   usage: tprof [-h] -t target [-x | --baseline path] [--json path]
                [--fail-above duration] [-m module]
                [script] ...

   positional arguments:
     script                Python script to run
     args                  Arguments to pass to the script or module

   options:
     -h, --help            show this help message and exit
     -t target             Target callable to profile (format: module:function).
     -x, --compare         Compare performance of targets, with the first as
                           baseline.
     --baseline path       Compare against statistics from a previous run's
                           --json file.
     --json path           Write statistics as JSON to this file, or '-' for
                           stdout.
     --fail-above duration
                           Exit with status 1 if any target's median time exceeds
                           this duration, e.g. '5ms'.
     -m module             Run library module as a script (like python -m)

.. [[[end]]]

Comparison mode
^^^^^^^^^^^^^^^

Pass ``-x`` (``--compare``) to compare the performance of multiple target functions, with the first as the baseline, in an extra “delta” column.
For example, given this code:

.. code-block:: python

    def before():
        total = 0
        for i in range(100_000):
            total += i
        return total


    def after():
        return sum(range(100_000))


    for _ in range(100):
        before()
        after()

…you can run tprof like this to compare the two functions:

.. code-block:: console

    $ tprof -x -t before -t after -m example
    🎯 tprof results:
     function         calls total  median ± σ      min … max   delta
     example:before()   100 227ms   2ms ± 34μs   2ms … 2ms   -
     example:after()    100  86ms 856μs ± 15μs 835μs … 910μs -62.27%

JSON output
^^^^^^^^^^^

Pass ``--json <path>`` to also write the statistics to the given file as JSON, or ``-`` to write them to standard output.
The file contains a ``functions`` list with the name, call count, and total, minimum, maximum, median, and standard deviation of times, in nanoseconds, per target:

.. code-block:: json

    {
      "version": 1,
      "label": null,
      "functions": [
        {
          "name": "lib:maths",
          "calls": 2,
          "total_ns": 610622917,
          "min_ns": 304285875,
          "max_ns": 306337042,
          "median_ns": 305311458.5,
          "stdev_ns": 1450393.5
        }
      ]
    }

Baseline comparison mode
^^^^^^^^^^^^^^^^^^^^^^^^

Pass ``--baseline <path>`` with the ``--json`` output of a previous run to compare against that run, in an extra “delta” column that compares each function’s median against its median in the baseline run.
Use this to check the effect of a change to the profiled code:

.. code-block:: console

    $ tprof -t lib:maths --json before.json ./example.py
    ...
    $ tprof -t lib:maths --baseline before.json ./example.py
    ...
    🎯 tprof results:
     function    calls total  median ± σ     min … max     delta
     lib:maths()     2 592ms 296ms ± 2ms  294ms … 297ms -3.11%

Failure threshold
^^^^^^^^^^^^^^^^^

Pass ``--fail-above <duration>`` to make tprof exit with status 1 if any target’s median time exceeds the given duration, for use as a regression gate in CI.
Specify the duration as a number followed by a unit: ``ns``, ``us``, ``ms``, or ``s``:

.. code-block:: console

    $ tprof -t lib:maths --fail-above 250ms ./example.py
    ...
    tprof: lib:maths() median 305311458ns exceeds 250000000ns

API
---

``tprof(*targets, label=None, compare=False, json_path=None, baseline_path=None)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use this context manager / decorator within your code to perform profiling in a specific block.
The report is printed when the block ends, each time it ends.

Each item in ``targets`` may be a callable to profile, or a string reference to one that will be resolved with |pkgutil.resolve_name()|__.

.. |pkgutil.resolve_name()| replace:: ``pkgutil.resolve_name()``
__ https://docs.python.org/3.14/library/pkgutil.html#pkgutil.resolve_name

``label`` is an optional string to add to the report heading to distinguish multiple reports.

Set ``compare`` to ``True`` to enable comparison mode, as documented above in the CLI section.

Set ``json_path`` to a file path to also write the statistics as JSON, as documented above in the CLI section, or ``-`` for standard output.

Set ``baseline_path`` to the path of a previous run’s JSON statistics to enable baseline comparison mode, as documented above in the CLI section.
It cannot be combined with ``compare``.

The context manager yields a list that is populated when the block ends with a ``FunctionStats`` object per target, with attributes ``name``, ``calls``, ``total_ns``, ``min_ns``, ``max_ns``, ``median_ns``, and ``stdev_ns``.

For example, given this code:

.. code-block:: python

    from lib import maths

    from tprof import tprof

    print("Doing the maths…")
    with tprof(maths):
        maths()
    print("The maths has been done!")

…running it would produce output like:

.. code-block:: console

    $ python example.py
    Doing the maths…
    🎯 tprof results:
     function    calls total  median ± σ   min … max
     lib:maths()     1 305ms 305ms     305ms … 305ms
    The maths has been done!

Another example using comparison mode:

.. code-block:: python

    from tprof import tprof


    def before():
        total = 0
        for i in range(100_000):
            total += i
        return total


    def after():
        return sum(range(100_000))


    with tprof(before, after, compare=True):
        for _ in range(100):
            before()
            after()

…which produces output like:

.. code-block:: console

    $ python example.py
    🎯 tprof results:
     function          calls total  median ± σ      min … max delta
     __main__:before()   100 227ms   2ms ± 83μs   2ms … 3ms -
     __main__:after()    100  85ms 853μs ± 22μs 835μs … 1ms -62.35%

History
-------

When optimizing Python code, I found I was using this workflow:

1. Profile the whole program with a tool like `cProfile <https://docs.python.org/3.14/library/profile.html>`__ or `py-spy <https://github.com/benfred/py-spy>`__ to find slow functions.
2. Pick a function to optimize.
3. Make a change.
4. Re-profile the whole program to see if the changes helped.

This works fined but profiling the whole program again adds overhead, and picking out the one function’s stats from the report is extra work.
When I saw that Python 3.12’s |sys.monitoring2|__ allows tracking specific functions with low overhead, I created tprof to streamline this workflow, allowing the final step to re-profile just the target function.

.. |sys.monitoring2| replace:: ``sys.monitoring``
__ https://docs.python.org/3/library/sys.html#sys.monitoring

It also seemed a natural extension that tprof could compare multiple functions, supporting a nice microbenchmarking workflow.

Output inspired by `poop <https://github.com/andrewrk/poop>`__ and formatted nicely with `Rich <https://github.com/Textualize/rich#readme>`__.
