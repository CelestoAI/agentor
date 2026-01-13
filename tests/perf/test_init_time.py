import shutil
import subprocess
import time

import pytest


def test_cli_time():
    if shutil.which("celesto") is None:
        pytest.skip("celesto CLI is provided by the separate celesto package.")
    t0 = time.perf_counter()
    assert subprocess.check_call(["celesto", "--help"]) == 0
    t1 = time.perf_counter()
    assert t1 - t0 < 5, f"CLI must be superfast but took {t1 - t0:.4f} seconds"
