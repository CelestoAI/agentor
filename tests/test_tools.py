from unittest.mock import MagicMock, patch
from agentor.tools.base import BaseTool
from agentor.tools.weather import CurrentWeather
from agentor.tools.calculator import Calculator
from agentor.tools.time import CurrentTime
from agentor.mcp.server import LiteMCP
from agents import FunctionTool


def test_base_tool_conversion():
    """Test that BaseTool correctly converts to FunctionTool."""

    class SimpleTool(BaseTool):
        name = "simple_tool"
        description = "A simple tool"

        def run(self, x: int) -> int:
            """Returns x + 1"""
            return x + 1

    tool = SimpleTool()
    fn_tool = tool.to_function_tool()

    assert isinstance(fn_tool, FunctionTool)
    assert fn_tool.name == "simple_tool"
    assert fn_tool.description == "A simple tool"
    # Verify the wrapped function works
    assert tool.run(1) == 2


def test_calculator_tool():
    """Test the Calculator tool logic."""
    calc = Calculator()
    assert calc.run("add", 5, 3) == "8"
    assert calc.run("subtract", 10, 4) == "6"
    assert calc.run("multiply", 2, 3) == "6"
    assert calc.run("divide", 10, 2) == "5.0"
    assert "Error" in calc.run("divide", 5, 0)


def test_current_time_tool():
    """Test the CurrentTime tool."""
    time_tool = CurrentTime()
    # We just check it returns a string and doesn't crash
    result = time_tool.run("UTC")
    assert isinstance(result, str)
    assert "UTC" in result


def test_weather_tool_api_key():
    """Test CurrentWeather tool requires API key."""
    weather = CurrentWeather()  # No key
    assert "Error: API key is required" in weather.run("London")


def test_weather_tool_mock_api():
    """Test CurrentWeather tool with mocked API."""
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "location": {"name": "London"},
            "current": {"temp_c": 15.0, "condition": {"text": "Partly cloudy"}},
        }
        mock_client.get.return_value = mock_response

        weather = CurrentWeather(api_key="test-key")
        result = weather.run("London")

        assert result["location"]["name"] == "London"
        assert result["current"]["temp_c"] == 15.0


def test_tool_mcp_serving():
    """Test that serve() initializes LiteMCP correctly."""

    class McpTool(BaseTool):
        name = "mcp_tool"
        description = "MCP Tool"

        def run(self):
            pass

    tool = McpTool()

    # Mock LiteMCP.run to avoid blocking
    with patch("agentor.mcp.server.LiteMCP.run") as mock_run:
        tool.serve(port=9000)

        assert isinstance(tool._mcp_server, LiteMCP)
        assert tool._mcp_server.name == "mcp_tool"
        mock_run.assert_called_once_with(port=9000)
