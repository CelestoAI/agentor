import subprocess
import time


def test_import_time():
    t0 = time.perf_counter()
    assert subprocess.check_call(["uv", "run", "python", "-c", "import agentor"]) == 0
    t1 = time.perf_counter()
    assert t1 - t0 < 7, (
        f"Package import should take less than 5 seconds but took {t1 - t0:.4f} seconds"
    )


def test_cli_time():
    t0 = time.perf_counter()
    assert subprocess.check_call(["celesto", "--help"]) == 0
    t1 = time.perf_counter()
    assert t1 - t0 < 1, f"CLI must be superfast but took {t1 - t0:.4f} seconds"
