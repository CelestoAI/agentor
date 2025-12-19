import os
from unittest.mock import MagicMock, patch

from agentor.mcp.server import LiteMCP
from agentor.tools.base import BaseTool, capability
from agentor.tools.calculator import CalculatorTool
from agentor.tools.timezone import TimezoneTool
from agentor.tools.weather import GetWeatherTool


def test_base_tool_conversion():
    """Test that BaseTool correctly converts to FunctionTool."""

    class SimpleTool(BaseTool):
        name = "simple_tool"
        description = "A simple tool"

        @capability
        def increment(self, x: int) -> int:
            """Returns x + 1"""
            return x + 1

    tool = SimpleTool()
    assert tool.increment(x=1) == 2


def test_calculator_tool():
    """Test the Calculator tool logic."""
    calc = CalculatorTool()
    assert calc.add(5, 3) == "8"
    assert calc.subtract(10, 4) == "6"
    assert calc.multiply(2, 3) == "6"
    assert calc.divide(10, 2) == "5.0"
    assert "Error" in calc.divide(5, 0)

    # Test via dispatcher
    assert calc.add(a=5, b=3) == "8"
    assert calc.multiply(a=2, b=3) == "6"

    # Test to_openai_function
    functions = calc.to_openai_function()
    assert len(functions) == 4  # add, subtract, multiply, divide
    names = [f.name for f in functions]
    assert "add" in names
    assert "subtract" in names
    assert "multiply" in names
    assert "divide" in names


def test_timezone_tool():
    """Test the TimezoneTool."""
    time_tool = TimezoneTool()
    # We just check it returns a string and doesn't crash
    result = time_tool.get_current_time("UTC")
    assert isinstance(result, str)
    assert "UTC" in result

    # Test via dispatcher
    result = time_tool.get_current_time(timezone="UTC")
    assert isinstance(result, str)
    assert "UTC" in result


def test_weather_tool_api_key():
    """Test WeatherAPI tool requires API key."""
    with patch.dict(os.environ, {"WEATHER_API_KEY": ""}):
        weather = GetWeatherTool()  # No key available
        result = weather.get_current_weather("London")

    assert "Error: API key is required" in result


def test_weather_tool_mock_api():
    """Test WeatherAPI tool with mocked API."""
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "location": {"name": "London", "country": "UK"},
            "current": {
                "temp_c": 15.0,
                "temp_f": 59.0,
                "condition": {"text": "Partly cloudy"},
                "humidity": 70,
                "wind_kph": 10,
            },
        }
        mock_client.get.return_value = mock_response

        weather = GetWeatherTool(api_key="test-key")
        result = weather.get_current_weather("London")

        assert "London" in result
        assert "15.0°C" in result
        assert "Partly cloudy" in result


def test_tool_mcp_serving():
    """Test that serve() initializes LiteMCP correctly."""

    class McpTool(BaseTool):
        name = "mcp_tool"
        description = "MCP Tool"

        @capability
        def do_something(self):
            """Does something"""
            pass

    tool = McpTool()

    # Mock LiteMCP.run to avoid blocking
    with patch("agentor.mcp.server.LiteMCP.run") as mock_run:
        tool.serve(port=9000)

        assert isinstance(tool._mcp_server, LiteMCP)
        assert tool._mcp_server.name == "mcp_tool"
        mock_run.assert_called_once_with(port=9000)
