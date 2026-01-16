#!/usr/bin/env python3

"""
A crude benchmark comparing async frameworks when sending messages
from the event loop to a dedicated worker thread and back again
"""

# what we benchmark
import asyncio
import uvloop
import trio
import anyio

# modules used
import queue
import resource
import time
import threading
import sys

# controllers for each framework


class AsyncIO:
    def __init__(self):
        self.queue = queue.SimpleQueue()
        self.loop = asyncio.get_running_loop()
        threading.Thread(target=self.worker_thread_run, args=(self.queue,)).start()

    def send(self, call):
        future = self.loop.create_future()
        self.queue.put((future, call))
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
        # needed to call back into trio/anyio
        "token",
        # Event used to signal ready
        "event",
        # result value
        "result",
        # call to make
        "call",
    )

    def __init__(self, token, event, call):
        self.token = token
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
        threading.Thread(target=self.worker_thread_run, args=(self.queue,)).start()

    def send(self, call):
        future = Future(trio.lowlevel.current_trio_token(), trio.Event(), call)
        self.queue.put(future)
        return future

    def close(self):
        self.queue.put(None)

    def worker_thread_run(self, q):
        while (future := q.get()) is not None:
            future.result = future.call()
            future.token.run_sync_soon(future.event.set)


class AnyIO:
    def __init__(self):
        self.queue = queue.SimpleQueue()
        threading.Thread(target=self.worker_thread_run, args=(self.queue,)).start()

    def send(self, call):
        future = Future(anyio.lowlevel.current_token(), anyio.Event(), call)
        self.queue.put(future)
        return future

    def close(self):
        self.queue.put(None)

    def worker_thread_run(self, q):
        while (future := q.get()) is not None:
            future.result = future.call()
            anyio.from_thread.run_sync(future.event.set, token=future.token)


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


def get_times():
    # returns wall time, all cpu time, and foreground thread only
    return (
        time.monotonic(),
        time.process_time(),
        resource.getrusage(resource.RUSAGE_THREAD).ru_utime,
    )


async def actual_benchmark():
    controller = Auto()

    start = get_times()

    # this releases and reacquires the GIL emulating
    # why you would need a dedicated worker thread
    work = lambda: time.sleep(0)

    for i in range(100_000):
        await controller.send(work)

    end = get_times()

    controller.close()

    return start, end


print(
    f"{'Framework':>25s} {'Wall':>8s} {'CpuTotal':>10s} {'CpuEvtLoop':>12s} {'CpuWorker':>12s}"
)


def show(framework, start, end):
    wall = end[0] - start[0]
    cpu_total = end[1] - start[1]
    cpu_async = end[2] - start[2]
    cpu_worker = cpu_total - cpu_async
    print(
        f"{framework:>25s} {wall:8.3f} {cpu_total:10.3f} {cpu_async:>12.3f} {cpu_worker:>12.3f}"
    )


start, end = asyncio.run(actual_benchmark())
show("asyncio", start, end)
start, end = asyncio.run(actual_benchmark(), loop_factory=uvloop.new_event_loop)
show("asyncio uvloop", start, end)
start, end = trio.run(actual_benchmark)
show("trio", start, end)
start, end = anyio.run(actual_benchmark, backend="asyncio")
show("anyio asyncio", start, end)
start, end = anyio.run(actual_benchmark, backend="asyncio", backend_options={"use_uvloop": True})
show("anyio asyncio uvloop", start, end)
start, end = anyio.run(actual_benchmark, backend="trio")
show("anyio trio", start, end)


