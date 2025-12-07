import subprocess


def test_cli():
    assert subprocess.check_call(["celesto", "--help"]) == 0, "celesto command failed"
