.. contents::

Purpose
=======

This is measuring the overhead of sending calls from the async
environment into a sync environment for execution and awaitable
response.  Finding ways of reducing that overhead will be nice.

When using a Python async framework, there are situations where
synchronous code needs to be run in a background thread.  If you do
not need the same thread for each call, then the async frameworks
provide that functionality such as `asyncio.to_thread
<https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread>`__
and `trio.to_thread.run_sync
<https://trio.readthedocs.io/en/stable/reference-core.html#trio.to_thread.run_sync>`__.

They do not provide having a dedicated worker thread which is required
for some code.  The bench provides code that shows how to do dedicated
worker thread calls, but note it does not implement cancellations,
timeouts, returning exceptions etc.  You can find complete
implementations in `the APSW source code
<https://github.com/rogerbinns/apsw/blob/async/apsw/aio.py>`__.
However I have not found a significant difference in results between
the full implementation and this abbreviated one.

Running
=======

This only runs on a Linux like platform.  ``uvloop`` is optional.

.. code-block:: console

    $ git clone https://github.com/rogerbinns/python-async-bench.git
    $ cd python-async-bench
    $ python3 -m venv .venv
    $ . .venv/bin/activate
    $ pip install trio anyio uvloop
    $ python3 bench.py

Customising
===========

Near the bottom of bench.py are two tweaks

COUNT

    How many messages to send to the thread

WORK

    What to do in the thread.  For example ``time.sleep(0)``
    releases and immediately reacquires the GIL.

Unrepresentative
================

Like all benchmarks, this is not reality, and only your own code and
data should be used to make decisions.  It is measuring the overhead
of sending the messages, and not doing meaningful work in the calls,
whereas meaningful work is the point of code.

It also sends a call and then awaits the results before doing the next
one.  That has no concurrency and the point of async is to get
concurrency!

Output description
==================

The output shows operating system reported measurements.  The time to
start and stop the event loops and threads is deliberately not
included because they would be long running in real world code.

Note that there will be variability in the numbers of each run because
modern computers have multiple cores running at multiple speeds
constantly balancing performance, work, and energy consumption.

Framework

    Shows what was run.  If it ends with ``to_thread`` then the
    framework method to send to any thread is used, otherwise a
    dedicated worker thread is used.

    `asyncio <https://docs.python.org/3/library/asyncio.html>`__ is
    included with Python.  Its internal loop can be replaced with
    `uvloop <https://uvloop.readthedocs.io/>`__.  `trio
    <https://trio.readthedocs.io>`__ provides a better API.  `anyio
    <https://anyio.readthedocs.io>`__ gives a similar API to trio, but
    lets your code be agnostic about what actual async event loop is
    running.

Wall

    How long it took to run using a wall clock.

CpuTotal

    Total CPU time consumed

CpuEvtLoop

    CPU time consumed in the foreground event loop - ie where async
    code runs and ``await`` is used.  This includes creating and
    sending packaged calls, and code behind ``await``.

CpuWorker

    CPU time consumed in background thread, which includes receiving
    packaged calls, calling them, and telling the async framework to
    return the result back to the event loop

Example run
===========

This is a run with 250,000 messages passed where the call just
returned zero.

.. code-block:: console

                      Framework     Wall   CpuTotal   CpuEvtLoop    CpuWorker
                        asyncio    4.951      5.131        2.207        2.923
                 asyncio uvloop    3.311      3.388        1.073        2.314
                           trio    8.074      9.039        5.540        3.498
                  anyio asyncio   11.133     13.315        5.537        7.778
           anyio asyncio uvloop    6.854      7.773        2.785        4.988
                     anyio trio   12.390     14.400        7.436        6.964
              asyncio to_thread   10.141     11.659        6.013        5.646
       asyncio uvloop to_thread    8.587      9.754        5.150        4.604
                 trio to_thread   15.629     16.665       10.603        6.063
        anyio asyncio to_thread   13.003     13.670        9.358        4.312
 anyio asyncio uvloop to_thread    8.630      9.136        5.772        3.364
           anyio trio to_thread   17.083     18.124       11.202        6.922

PyPY
====

PyPY doesn't provide the information necessary to distinguish between
event loop thread and worker thread CPU consumption, so it is all
shown as event loop.