import pytest

from mechparts.config import Settings
from mechparts.core.runner import ProcessRunner, RunnerTimeout
from mechparts.service import PartService
from slow_jobs import sleep_then_return


def test_process_runner_times_out_and_recovers():
    runner = ProcessRunner(workers=1, timeout=3)
    try:
        assert runner.run(sleep_then_return, 0, 1) == 1  # warm up the worker
        with pytest.raises(RunnerTimeout):
            runner.run(sleep_then_return, 30, 2)
        assert runner.run(sleep_then_return, 0, 3) == 3  # a fresh pool after the kill
    finally:
        runner.close()


def test_generation_in_worker_process(tmp_path):
    service = PartService(Settings(data_dir=tmp_path, workers=1, timeout=120))
    try:
        r = service.generate_part("l_bracket", {}, "step")
        assert r.watertight and r.bounding_box.size == [30.0, 20.0, 30.0]
    finally:
        service.close()
