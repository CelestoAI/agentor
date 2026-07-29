import shutil
import subprocess
import sys
import time

import pytest

#: `import agentor` measures ~2ms locally; reaching the engine costs ~1900ms.
#: The bound sits well clear of the first and well under the second, so it
#: survives a slow CI runner but still catches an eager engine import.
_BARE_IMPORT_BUDGET_S = 0.3


def test_importing_agentor_does_not_pull_the_engine() -> None:
    """The lazy `__getattr__` in agentor/__init__.py has to keep paying off.

    Nothing else guarded this. A plain `from agentor.engine... import` added at
    module scope would take the top-level import from milliseconds to seconds,
    and every `agentor.tools` and CLI user would pay for it.
    """
    elapsed = _time_import("import agentor")
    assert elapsed < _BARE_IMPORT_BUDGET_S, (
        f"`import agentor` took {elapsed:.3f}s, over the {_BARE_IMPORT_BUDGET_S}s "
        "budget - something at module scope is importing the engine or litellm"
    )


def test_the_engine_is_reachable_but_only_on_demand() -> None:
    """Guards the other half: the cheap import must still resolve Agentor.

    `check_call` raises on a non-zero exit, so the call is the assertion. It
    stays outside an `assert` on purpose - `python -O` strips those, which would
    skip the subprocess and leave the test passing without running anything.
    """
    subprocess.check_call([sys.executable, "-c", "import agentor; agentor.Agentor"])


def _time_import(statement: str) -> float:
    """Best of three in a fresh interpreter, so no earlier import warms it."""
    program = (
        f"import time; t = time.perf_counter(); {statement}; "
        "print(time.perf_counter() - t)"
    )
    samples = []
    for _ in range(3):
        result = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
        )
        samples.append(float(result.stdout))
    return min(samples)


def test_cli_time() -> None:
    if shutil.which("celesto") is None:
        pytest.skip("celesto CLI is provided by the separate celesto package.")
    t0 = time.perf_counter()
    subprocess.check_call(["celesto", "--help"])  # raises on failure; see above
    t1 = time.perf_counter()
    assert t1 - t0 < 5, f"CLI must be superfast but took {t1 - t0:.4f} seconds"
