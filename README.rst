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
                        asyncio    4.964      5.204        2.187        3.017
                 asyncio uvloop    3.537      3.647        1.095        2.552
                           trio    7.837      8.744        5.406        3.338
                  anyio asyncio   10.101     12.352        4.889        7.463
           anyio asyncio uvloop    6.134      7.292        2.312        4.979
                     anyio trio   11.246     13.600        6.724        6.876
              asyncio to_thread    9.606     11.039        5.519        5.520
       asyncio uvloop to_thread    7.955      9.128        4.338        4.789
                 trio to_thread   15.310     16.343       10.602        5.741
        anyio asyncio to_thread   12.961     13.755        9.737        4.018
 anyio asyncio uvloop to_thread    9.002      9.594        6.214        3.380
           anyio trio to_thread   16.266     17.586       11.241        6.345


PyPY
====

PyPY doesn't provide the information necessary to distinguish between
event loop thread and worker thread CPU consumption, so it is all
shown as event loop.