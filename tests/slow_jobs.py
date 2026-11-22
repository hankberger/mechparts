"""Top-level job functions for runner tests (importable by spawned worker processes)."""

import time


def sleep_then_return(seconds: float, value: int) -> int:
    time.sleep(seconds)
    return value
