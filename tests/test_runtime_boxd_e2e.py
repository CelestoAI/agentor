"""Live test for BoxdRuntime against a real boxd machine.

Skipped unless BOXD_E2E=1. Needs BOXD_API_KEY (and BOXD_ORG if the key can
reach more than one org). Creates one machine and deletes it again.
"""

import os
import uuid

import pytest

from agentor.runtime import BoxdRuntime
from agentor.tools.shell import ShellCommandRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("BOXD_E2E") != "1", reason="set BOXD_E2E=1 to run against boxd"
)


def test_boxd_runtime_live():
    boxd = pytest.importorskip("boxd")
    prefix = os.environ.get("BOXD_E2E_NAME_PREFIX", "agentor-e2e-")
    create_kwargs = {"name": f"{prefix}{uuid.uuid4().hex[:8]}"}
    if os.environ.get("BOXD_ORG"):
        create_kwargs["org"] = os.environ["BOXD_ORG"]

    runtime = BoxdRuntime(
        region=os.environ.get("BOXD_E2E_REGION", "fra"), **create_kwargs
    )
    print(f"boxd machine {runtime.machine_id}")
    try:
        output = runtime(
            ShellCommandRequest(
                command='echo "$GREETING" | tr a-z A-Z; pwd; echo oops >&2; exit 3',
                working_directory="/tmp",
                env={"GREETING": "hello from agentor"},
            )
        )
        assert output == "HELLO FROM AGENTOR\n/tmp\noops\n"

        machine = runtime.client.machines.get(runtime.machine_id)
        assert machine.status == "running"
        assert machine.networking.isolated is True
    finally:
        runtime.close()

    with pytest.raises(boxd.NotFoundError):
        runtime.client.machines.get(runtime.machine_id)
