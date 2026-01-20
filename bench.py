#!/usr/bin/env python3

"""
A crude benchmark comparing async frameworks when sending messages
from the event loop to a dedicated worker thread and back again
"""

# what we benchmark
import asyncio
import trio
import anyio

try:
    import uvloop
except ImportError:
    uvloop = None

# modules used
import queue
import resource
import functools
import time
import threading
import sys

# controllers for each framework


class AsyncIO:
    def __init__(self):
        self.queue = queue.SimpleQueue()
        self.loop = asyncio.get_running_loop()
        threading.Thread(target=self.worker_thread_run, args=(self.queue,)).start()

    def send(self, func, *args, **kwargs):
        future = self.loop.create_future()
        self.queue.put((future, functools.partial(func, *args, **kwargs)))
        return future

    def close(self):
        self.queue.put(None)

    def worker_thread_run(self, q):
        while (item := q.get()) is not None:
            future, call = item

            self.loop.call_soon_threadsafe(self.set_future_result, future, call())

    def set_future_result(self, future, result):
        if not future.done():
            future.set_result(result)


# Trio and AnyIO need a custom Future


class Future:
    __slots__ = (
        # Event used to signal ready
        "event",
        # result value
        "result",
        # call to make
        "call",
    )

    def __init__(self, event, call):
        self.event = event
        self.call = call

    async def aresult(self):
        await self.event.wait()
        return self.result

    def __await__(self):
        return self.aresult().__await__()


class Trio:
    def __init__(self):
        self.queue = queue.SimpleQueue()
        self.token = trio.lowlevel.current_trio_token()
        threading.Thread(target=self.worker_thread_run, args=(self.queue,)).start()

    def send(self, func, *args, **kwargs):
        future = Future(
            trio.Event(),
            functools.partial(func, *args, **kwargs),
        )
        self.queue.put(future)
        return future

    def close(self):
        self.queue.put(None)

    def worker_thread_run(self, q):
        while (future := q.get()) is not None:
            future.result = future.call()
            self.token.run_sync_soon(future.event.set)


class AnyIO:
    def __init__(self):
        self.queue = queue.SimpleQueue()
        self.token = anyio.lowlevel.current_token()
        threading.Thread(target=self.worker_thread_run, args=(self.queue,)).start()

    def send(self, func, *args, **kwargs):
        future = Future(
            anyio.Event(),
            functools.partial(func, *args, **kwargs),
        )
        self.queue.put(future)
        return future

    def close(self):
        self.queue.put(None)

    def worker_thread_run(self, q):
        while (future := q.get()) is not None:
            future.result = future.call()
            anyio.from_thread.run_sync(future.event.set, token=self.token)


def Auto():
    # anyio works with trio and asyncio, so we detect it first, and only
    # it does the the run.  this code is ugly
    try:
        anyio_run_code = anyio.run.__code__

        frame = sys._getframe()
        while frame:
            if frame.f_code is anyio_run_code:
                return AnyIO()
            frame = frame.f_back
    except:
        pass

    try:
        trio.lowlevel.current_trio_token()
        return Trio()
    except:
        pass

    try:
        asyncio.get_running_loop()
        return AsyncIO()
    except:
        pass

    raise RuntimeError("Unable to determine current Async framework")


if sys.implementation.name != "pypy":

    def get_times():
        # returns wall time, all cpu time, and foreground thread only
        return (
            time.monotonic(),
            time.process_time(),
            resource.getrusage(resource.RUSAGE_THREAD).ru_utime,
        )
else:

    def get_times():
        return (time.monotonic(), time.process_time(), time.process_time())


async def dedicated_thread(count, func, *args, **kwargs):
    controller = Auto()

    # check it works and don't include thread startup time
    assert 7 == await controller.send(lambda x: x + 2, 5)

    start = get_times()

    for i in range(count):
        await controller.send(func, *args, **kwargs)

    end = get_times()

    controller.close()

    return start, end


async def to_thread(sender, count, func, *args, **kwargs):
    # check it works and don't include thread startup time
    assert 7 == await sender(lambda x: x + 2, 5)

    start = get_times()

    for i in range(count):
        await sender(func, *args, **kwargs)

    end = get_times()

    return start, end


def run_benchmark():
    print(
        f"{'Framework':>30s} {'Wall':>8s} {'CpuTotal':>10s} {'CpuEvtLoop':>12s} {'CpuWorker':>12s}"
    )

    def show(framework, start, end):
        wall = end[0] - start[0]
        cpu_total = end[1] - start[1]
        cpu_async = end[2] - start[2]
        cpu_worker = cpu_total - cpu_async
        print(
            f"{framework:>30s} {wall:8.3f} {cpu_total:10.3f} {cpu_async:>12.3f} {cpu_worker:>12.3f}"
        )

    start, end = asyncio.run(dedicated_thread(COUNT, *WORK))
    show("asyncio", start, end)
    if uvloop:
        start, end = asyncio.run(
            dedicated_thread(COUNT, *WORK), loop_factory=uvloop.new_event_loop
        )
        show("asyncio uvloop", start, end)
    start, end = trio.run(dedicated_thread, COUNT, *WORK)
    show("trio", start, end)
    start, end = anyio.run(dedicated_thread, COUNT, *WORK, backend="asyncio")
    show("anyio asyncio", start, end)
    if uvloop:
        start, end = anyio.run(
            dedicated_thread,
            COUNT,
            *WORK,
            backend="asyncio",
            backend_options={"use_uvloop": True},
        )
        show("anyio asyncio uvloop", start, end)
    start, end = anyio.run(dedicated_thread, COUNT, *WORK, backend="trio")
    show("anyio trio", start, end)

    start, end = asyncio.run(to_thread(asyncio.to_thread, COUNT, *WORK))
    show("asyncio to_thread", start, end)
    if uvloop:
        start, end = asyncio.run(
            to_thread(asyncio.to_thread, COUNT, *WORK),
            loop_factory=uvloop.new_event_loop,
        )
        show("asyncio uvloop to_thread", start, end)
    start, end = trio.run(to_thread, trio.to_thread.run_sync, COUNT, *WORK)
    show("trio to_thread", start, end)
    start, end = anyio.run(
        to_thread, anyio.to_thread.run_sync, COUNT, *WORK, backend="asyncio"
    )
    show("anyio asyncio to_thread", start, end)
    if uvloop:
        start, end = anyio.run(
            to_thread,
            anyio.to_thread.run_sync,
            COUNT,
            *WORK,
            backend="asyncio",
            backend_options={"use_uvloop": True},
        )
        show("anyio asyncio uvloop to_thread", start, end)
    start, end = anyio.run(
        to_thread, anyio.to_thread.run_sync, COUNT, *WORK, backend="trio"
    )
    show("anyio trio to_thread", start, end)


### How many messages are sent
COUNT = 250_000

### What work to do in the thread

# this releases and reacquires the GIL
# WORK = (time.sleep, 0)

# this just returns zero
WORK = (lambda: 0,)

run_benchmark()
