from agentor import tool
from agentor.tool_search import ToolSearch


@tool
def alpha() -> str:
    """First tool description."""
    return "alpha"


@tool
def beta() -> str:
    """Second tool description about weather."""
    return "beta"


def test_tool_search_returns_matching_tool():
    search = ToolSearch()
    search.add(alpha)
    search.add(beta)

    result = search.search("weather")
    assert result is not None
    assert result["tool"].name == "beta"
    assert "weather" in result["tool"].description


def test_tool_search_to_function_tool_reuses_wrapper():
    search = ToolSearch()
    search.add(alpha)
    wrapper1 = search.to_function_tool()
    wrapper2 = search.to_function_tool()
    assert wrapper1 is wrapper2
