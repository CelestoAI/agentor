import os
from typing import Optional

import httpx

from agentor.tools.base import BaseTool, capability


class GetWeatherTool(BaseTool):
    name = "weather"
    description = "Get current weather information for a location"

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            api_key = os.environ.get("WEATHER_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API key is required to use this tool. Create an account at https://www.weatherapi.com/ and get your API key."
            )
        super().__init__(api_key)

    @capability
    def get_current_weather(self, location: str) -> str:
        """
        Get the current weather for a location using WeatherAPI.com.

        Args:
            location: The location to get the weather for (e.g. 'London', 'Paris').
        """
        if not self.api_key:
            return "Error: API key is required for this tool. Create an account at https://www.weatherapi.com/ and get your API key."

        base_url = "http://api.weatherapi.com/v1/current.json"
        params = {"key": self.api_key, "q": location}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()

                # Format response for better readability
                current = data.get("current", {})
                location_data = data.get("location", {})

                return f"""Weather in {location_data.get("name")}, {location_data.get("country")}:
Temperature: {current.get("temp_c")}°C ({current.get("temp_f")}°F)
Condition: {current.get("condition", {}).get("text")}
Humidity: {current.get("humidity")}%
Wind: {current.get("wind_kph")} km/h"""
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"
