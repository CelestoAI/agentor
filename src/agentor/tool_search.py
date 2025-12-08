from __future__ import annotations

from typing import Dict, List, Optional

import bm25s
import Stemmer

from agentor.core.tool import BaseTool


class ToolSearch:
    """Enable tool search capability in your LLM.

    >>> from agentor import ToolSearch, LLM, tool
    >>> @tool
    ... def get_weather(city: str):
    ...     return "The weather in London is sunny"
    >>> tool_search = ToolSearch()
    >>> tool_search.add(get_weather)
    >>> llm = LLM(model="gpt-5-mini", api_key="test")
    >>> llm.chat("What is the weather in London?")
    >>> # output: {"name": "get_weather", "description": "The weather in London is sunny"}
    """

    def __init__(self) -> None:
        self._tools: List[BaseTool] = []
        self._stemmer = Stemmer.Stemmer("english")
        self._retriever = None
        self._tool_wrapper: Optional[BaseTool] = None

    def _build_retriever(self) -> None:
        """Build a BM25 retriever over the added tools."""
        corpus = [tool.name + "\n\n" + (tool.description or "") for tool in self._tools]
        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", stemmer=self._stemmer)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        self._retriever = retriever

    def add(self, tool: BaseTool) -> None:
        """Add a tool to the search index."""
        self._tools.append(tool)
        self._retriever = None  # rebuild on next search

    def search(
        self, query: str, score_threshold: float = 0.25
    ) -> Optional[Dict[str, str]]:
        """Search for a tool based on a natural language query."""
        if not self._tools:
            return None

        if self._retriever is None:
            self._build_retriever()

        query_tokens = bm25s.tokenize(query, stemmer=self._stemmer)
        results, scores = self._retriever.retrieve(
            query_tokens, k=min(10, len(self._tools))
        )

        for i in range(results.shape[1]):
            doc, score = results[0, i], scores[0, i]
            if score >= score_threshold:
                match = self._tools[int(doc)]
                return {
                    "tool_index": int(doc),
                    "tool": match,
                    "type": "tool_search_output",
                }
        return None

    def to_function_tool(self) -> BaseTool:
        """Expose the search capability as a tool callable by the LLM or Agentor."""
        if self._retriever is None:
            self._build_retriever()
        if self._tool_wrapper is None:

            def _search(
                query: str, score_threshold: float = 0.1
            ) -> Optional[Dict[str, str]]:
                """
                Search for a tool based on a query.
                Args:
                    query: The query to search for a tool.
                    score_threshold: The threshold for the score of the tool.
                """
                return self.search(query, score_threshold)

            self._tool_wrapper = BaseTool.from_function(
                _search,
                name="tool_search",
                description="Search for a tool based on a query.",
            )
        return self._tool_wrapper
