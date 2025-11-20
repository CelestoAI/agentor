import httpx
from agentor.tools.base import BaseTool
from typing import Optional, Any


class CurrentWeather(BaseTool):
    name = "get_weather"
    description = "Get the current weather for a location"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

    def run(self, location: str) -> Any:
        """
        Get the current weather for a location using WeatherAPI.com.

        Args:
            location: The location to get the weather for (e.g. 'London', 'Paris').
        """
        if not self.api_key:
            return "Error: API key is required for this tool."

        base_url = "http://api.weatherapi.com/v1/current.json"
        params = {"key": self.api_key, "q": location}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(base_url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"
