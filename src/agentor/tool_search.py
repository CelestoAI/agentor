import bm25s
import Stemmer

from agentor.tools.base import BaseTool, capability


class ToolSearch(BaseTool):
    name = "tool_search"
    description = "Search for tools based on a query"

    def __init__(self):
        super().__init__()
        self._collection_name = "tool_search"
        self._tools = list[BaseTool]()
        self._stemmer = Stemmer.Stemmer("english")
        self._retriever = None

    def _update_description(self) -> None:
        capabilities = [
            func
            for func in dir(self)
            if callable(getattr(self, func))
            and getattr(getattr(self, func), "_is_capability", False)
        ]
        if capabilities:
            self.description += "\n\nAvailable capabilities: " + ", ".join(capabilities)
            for capability in capabilities:
                self.description += f"- {capability}\n"

    def _build_retriever(self) -> None:
        corpus = [tool.name + "\n\n" + tool.description for tool in self._tools]
        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", stemmer=self._stemmer)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        self._retriever = retriever
        self._update_description()

    def add(self, tool: BaseTool) -> None:
        self._tools.append(tool)

    def search(self, query: str, score_threshold: float = 0.25):
        if self._retriever is None:
            print("Building retriever")
            self._build_retriever()

        query_tokens = bm25s.tokenize(query, stemmer=self._stemmer)
        results, scores = self._retriever.retrieve(
            query_tokens, k=min(10, len(self._tools))
        )
        for i in range(results.shape[1]):
            doc, score = results[0, i], scores[0, i]
            if score >= score_threshold:
                return self._tools[int(doc)].to_function_tool()
        return None

    @capability
    def tool(self, query: str, score_threshold: float = 0.25):
        """
        Search for a tool based on a query and return the tool.
        Args:
            query: The query to search for a tool.
            score_threshold: The threshold for the score of the tool.
        Returns:
            The tool if found, otherwise None.
        """
        tool = self.search(query, score_threshold)
        if tool is not None:
            return tool.run(query)
        return None
