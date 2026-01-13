import shutil
import subprocess

import pytest


def test_cli():
    if shutil.which("celesto") is None:
        pytest.skip("celesto CLI is provided by the separate celesto package.")
    assert subprocess.check_call(["celesto", "--help"]) == 0, "celesto command failed"
