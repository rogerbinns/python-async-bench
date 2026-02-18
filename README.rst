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
    framework method to send to a thread pool is used, otherwise a
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
                           asyncio    5.884      6.132        2.744        3.388
                    asyncio uvloop    3.470      3.648        1.155        2.493
                              trio    8.256      9.280        5.760        3.520
                     anyio asyncio   11.528     13.893        5.812        8.080
              anyio asyncio uvloop    6.454      7.630        2.555        5.075
                        anyio trio   12.171     14.555        7.529        7.026
                 asyncio to_thread   10.683     12.326        6.651        5.675
          asyncio uvloop to_thread    9.090     10.548        5.244        5.303
                    trio to_thread   16.837     18.245       11.642        6.603
           anyio asyncio to_thread   14.282     15.160       10.532        4.628
    anyio asyncio uvloop to_thread    9.577     10.326        6.723        3.603
              anyio trio to_thread   18.036     19.437       12.271        7.166


PyPY
====

PyPY doesn't provide the information necessary to distinguish between
event loop thread and worker thread CPU consumption, so it is all
shown as event loop.