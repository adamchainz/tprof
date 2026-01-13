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

.. |sys.monitoring| replace:: ``sys.monitoring``
__ https://docs.python.org/3/library/sys.html#sys.monitoring

tprof supports usage as a CLI and with a Python API.

CLI
^^^

Specify one or more target functions with ``-t``, then what to run: a script file by filename, or a module with ``-m`` then its name.
Any extra arguments are passed to the script or module.

.. code-block:: console

    $ tprof -t lib:maths ./example.py
    ...
    🎯 tprof results:
     function    calls total  mean ± σ     min … max
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

   usage: tprof [-h] -t target (-m module | script) ...

   positional arguments:
     script      Python script to run
     args        Arguments to pass to the script or module

   options:
     -h, --help  show this help message and exit
     -t target   Target callable to profile (format: module:function).
     -m module   Run library module as a script (like python -m)

.. [[[end]]]

API
^^^

Use ``tprof.tprof`` as a context manager, passing the list of target functions.

.. code-block:: python

    from tprof import tprof

    from lib import maths


    def main():
        with tprof(maths):
            ...
            maths()
            ...


    if __name__ == "__main__":
        main()

Targets can be specified as strings or callables.
