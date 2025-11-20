from agentor.tools.base import BaseTool


class CurrentWeather(BaseTool):
    name = "get_weather"
    description = "Get the current weather for a location"

    def run(self, location: str, unit: str = "celsius") -> str:
        """
        Get the current weather for a location.

        Args:
            location: The city and state, e.g. San Francisco, CA
            unit: The unit of temperature, either 'celsius' or 'fahrenheit'
        """
        # Mock implementation for demonstration
        return f"The weather in {location} is sunny and 25 degrees {unit}."
