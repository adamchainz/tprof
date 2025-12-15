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

    $ tprof -t lib.math ./example.py
    ...
    🎯 tprof results:
      lib:maths(): 608ms

API
^^^

Use ``trprof.tprof`` as a context manager, passing the list of target functions.

.. code-block:: python

    import time

    from tprof import tprof


    def maths():
        time.sleep(0.3)


    def main():
        with tprof(maths):
            print("Doing maths")
            maths()
            print("And again")
            maths()


    if __name__ == "__main__":
        main()

Targets can be specified as strings or callables.
