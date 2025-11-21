from typing import Optional

from agentor.tools.base import BaseTool, capability

try:
    from exa_py import Exa
except ImportError:
    Exa = None


class ExaSearchTool(BaseTool):
    name = "exa_search"
    description = "Search the web using Exa API."

    def __init__(self, api_key: Optional[str] = None):
        if Exa is None:
            raise ImportError(
                "Exa dependency is missing. Please install it with `pip install agentor[exa]`."
            )
        super().__init__(api_key)
        self.client = Exa(api_key=api_key)

    @capability
    def search(self, query: str, num_results: int = 5) -> str:
        """
        Search the web for the given query.

        Args:
            query: The search query.
            num_results: The number of results to return.
        """
        try:
            response = self.client.search(
                query,
                num_results=num_results,
                use_autoprompt=True,
            )
            return str(response)
        except Exception as e:
            return f"Error performing search: {str(e)}"
