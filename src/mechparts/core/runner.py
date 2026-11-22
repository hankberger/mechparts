"""Runs geometry generation, in worker processes with a hard timeout or inline.

CAD kernels can take a long time (or hang) on unusual inputs, and OCCT is not safe to
drive from several threads at once. The process runner keeps a small pool of worker
processes; if a job overruns its timeout the pool is killed and recreated, so one bad
request cannot wedge the server.
"""

from __future__ import annotations

import concurrent.futures
import multiprocessing
import threading
from concurrent.futures.process import BrokenProcessPool
from typing import Any, Callable, Protocol

from mechparts.core import registry
from mechparts.core.geometry import analyze, check_mesh, export_bytes


class RunnerTimeout(Exception):
    pass


class RunnerCrashed(Exception):
    pass


def produce(part_id: str, params: dict[str, Any], fmt: str, seed: str) -> tuple[dict[str, Any], float, bytes]:
    """Build, check and export one part. Runs in a worker process; raises GeometryError on bad output."""
    import logging

    logging.getLogger("build123d").setLevel(logging.WARNING)
    part = registry.get(part_id)
    if part is None:
        raise ValueError(f"Unknown part {part_id!r}")
    model = part.Params.model_validate(params)
    shape = part.build(model)
    info = analyze(shape)
    stl = export_bytes(shape, "stl", seed)
    check_mesh(stl)  # fails loudly if the mesh is not watertight / manifold
    data = stl if fmt == "stl" else export_bytes(shape, fmt, seed)  # type: ignore[arg-type]
    return info.bounding_box.model_dump(), info.volume_mm3, data


class Runner(Protocol):
    timeout: float

    def run(self, fn: Callable[..., Any], *args: Any) -> Any: ...
    def close(self) -> None: ...


class InlineRunner:
    """Runs jobs in the calling process, one at a time. No timeout; used for tests and debugging."""

    def __init__(self) -> None:
        self.timeout = 0.0
        self._lock = threading.Lock()

    def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        with self._lock:
            return fn(*args)

    def close(self) -> None:
        pass


class ProcessRunner:
    def __init__(self, workers: int, timeout: float):
        self.workers = workers
        self.timeout = timeout
        self._lock = threading.Lock()
        self._executor: concurrent.futures.ProcessPoolExecutor | None = None

    def _pool(self) -> concurrent.futures.ProcessPoolExecutor:
        with self._lock:
            if self._executor is None:
                # spawn behaves the same on Linux, macOS and Windows and is safe with threads.
                self._executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=self.workers, mp_context=multiprocessing.get_context("spawn")
                )
            return self._executor

    def _reset(self, executor: concurrent.futures.ProcessPoolExecutor) -> None:
        with self._lock:
            if self._executor is not executor:
                return
            self._executor = None
        for proc in list(getattr(executor, "_processes", {}).values()):
            proc.kill()
        executor.shutdown(wait=False, cancel_futures=True)

    def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        executor = self._pool()
        try:
            future = executor.submit(fn, *args)
            return future.result(timeout=self.timeout or None)
        except concurrent.futures.TimeoutError as err:
            self._reset(executor)
            raise RunnerTimeout(f"exceeded {self.timeout:g} s") from err
        except BrokenProcessPool as err:
            self._reset(executor)
            raise RunnerCrashed("worker process died") from err

    def close(self) -> None:
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)


def make_runner(workers: int, timeout: float) -> Runner:
    return ProcessRunner(workers, timeout) if workers > 0 else InlineRunner()
