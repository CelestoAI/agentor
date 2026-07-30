"""Regression tests for two bugs found auditing what the refactor left behind.

Both were invisible: one silenced the warning that announced it, the other
lived in the half of a decorator's signature nothing exercised.
"""

import importlib
import subprocess
import sys

import pytest

from agentor import tool


def test_importing_agentor_does_not_silence_the_host_applications_warnings() -> None:
    """`import agentor` used to install a process-wide DeprecationWarning ignore.

    A library has no business mutating global warning state, and this one
    suppressed nothing from agentor's own dependency graph - it only hid the
    warnings of whatever application imported it.

    Run in a subprocess: the filter was installed at import time, and this
    session has already imported agentor.

    Nothing here resets `warnings.filters`. `simplefilter`/`catch_warnings`
    would replace the list wholesale and take agentor's entry with it, so the
    test would pass against the bug it exists to catch.
    """
    program = """
import warnings
before = list(warnings.filters)
import agentor  # must not touch the global filter list
added = [f for f in warnings.filters if f not in before]
print("ADDED", added)

shown = []
warnings.showwarning = lambda *a, **k: shown.append(a[0])
warnings.warn("host application deprecation", DeprecationWarning)
print("SHOWN" if shown else "SWALLOWED")
"""
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    added, verdict = result.stdout.strip().splitlines()
    assert added == "ADDED []", f"importing agentor installed a global filter: {added}"
    assert verdict == "SHOWN", (
        f"importing agentor suppressed a warning it did not raise: {verdict}"
    )


def test_agentor_own_deprecation_warnings_reach_the_user() -> None:
    """The MCPServerStreamableHttp shim exists to warn; the warning must arrive.

    Captured by swapping `showwarning` rather than through `catch_warnings`,
    which resets the filters and would mask a global ignore.
    """
    program = """
import warnings
import agentor  # noqa: F401
from agentor.engine.mcp import MCPServerStreamableHttp

shown = []
warnings.showwarning = lambda *a, **k: shown.append(str(a[0]))
MCPServerStreamableHttp(params={"url": "http://example.invalid/mcp"})
print(";".join(shown))
"""
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    assert "deprecated" in result.stdout, (
        f"the deprecation notice never reached the caller: {result.stdout!r}"
    )


def test_tool_accepts_a_description_without_a_name() -> None:
    """`@tool(description=...)` raised AttributeError on the None func."""

    @tool(description="Looks up the weather")
    def get_weather(city: str) -> str:
        return f"sunny in {city}"

    assert get_weather.name == "get_weather", (
        "the name should fall back to the function"
    )
    assert get_weather.description == "Looks up the weather"


def test_tool_keeps_deriving_both_from_the_function() -> None:
    @tool
    def plain(x: str) -> str:
        """Docstring description."""
        return x

    assert plain.name == "plain"
    assert plain.description == "Docstring description."


def test_tool_still_honours_an_explicit_name() -> None:
    @tool(name="weather_lookup", description="Fetches weather data")
    def get_weather(city: str) -> str:
        return f"sunny in {city}"

    assert get_weather.name == "weather_lookup"
    assert get_weather.description == "Fetches weather data"


@pytest.mark.parametrize("attribute", ["_extract_tool_name", "_stringify_output"])
def test_the_openai_agents_item_probes_are_gone(attribute: str) -> None:
    """Both existed only to guess at opaque openai-agents stream items."""
    import agentor.output_text_formatter as formatter

    assert not hasattr(formatter, attribute), f"{attribute} came back; nothing calls it"


# ------------------------------------------------ retired Celesto platform


def test_celesto_sdk_is_gone_and_fails_like_any_missing_attribute() -> None:
    """It re-exported a class the current `celesto` package no longer defines.

    agentor requires `celesto>=0.0.2`, so a fresh install resolves 0.0.10, where
    `celesto.sdk.client.CelestoSDK` is gone. The re-export caught only
    ModuleNotFoundError - the module still imports - so users got a bare
    ImportError raised from inside a dependency.

    The assertion that matters is the exception *type*: anyone reinstating a
    re-export of a name the dependency dropped brings the ImportError back.
    """
    import agentor

    with pytest.raises(AttributeError) as caught:
        agentor.CelestoSDK

    assert "CelestoSDK" in str(caught.value)


def test_celesto_sdk_is_no_longer_advertised() -> None:
    import agentor

    assert "CelestoSDK" not in agentor.__all__
    assert "CelestoSDK" not in dir(agentor)


def test_nothing_in_the_package_imports_the_celesto_distribution() -> None:
    """CelestoSDK was its only importer, so the coupling should be gone.

    Guards the claim rather than the dependency: `celesto` remains installed as
    a transitive convenience, so importing it would still succeed here and pass
    by accident. Grep the sources instead.
    """
    import pathlib

    import agentor

    root = pathlib.Path(agentor.__file__).parent
    offenders = [
        f"{path.relative_to(root)}:{number}"
        for path in root.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if line.lstrip().startswith(("import celesto", "from celesto"))
    ]
    assert not offenders, f"agentor imports the celesto package at {offenders}"


def test_the_create_proxy_cli_module_is_gone() -> None:
    """`agentor.mcp.proxy` implemented the retired `create-proxy` command.

    No console script ever pointed at it, `agentor.mcp` never exported it, and
    nothing called it.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agentor.mcp.proxy")


def test_the_mcp_package_still_exports_what_callers_use() -> None:
    """Deleting proxy.py must not disturb the rest of agentor.mcp."""
    import agentor.mcp as mcp

    for name in ("MCPAPIRouter", "LiteMCP", "Context", "get_context", "MCPServer"):
        assert hasattr(mcp, name), f"{name} disappeared with proxy.py"
