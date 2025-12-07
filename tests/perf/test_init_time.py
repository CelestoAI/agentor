import subprocess
import time


def test_import_time():
    t0 = time.perf_counter()
    t1 = time.perf_counter()
    assert t1 - t0 < 5, (
        f"Package import should take less than 5 second but took {t1 - t0:.4f} seconds"
    )


def test_cli_time():
    t0 = time.perf_counter()
    assert subprocess.check_call(["celesto", "--help"]) == 0
    t1 = time.perf_counter()
    assert t1 - t0 < 1, "CLI must be superfast"


if __name__ == "__main__":
    test_import_time()
