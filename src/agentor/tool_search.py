import bm25s
import Stemmer

from agentor.tools.base import BaseTool


class ToolSearch:
    def __init__(self):
        self._collection_name = "tool_search"
        self._tools = list[BaseTool]()
        self._stemmer = Stemmer.Stemmer("english")
        self._retriever = None

    def _build_retriever(self) -> None:
        corpus = [tool.name + "\n\n" + tool.description for tool in self._tools]
        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", stemmer=self._stemmer)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        self._retriever = retriever

    def add(self, tool: BaseTool) -> None:
        self._tools.append(tool)

    def search(self, query: str, score_threshold: float = 0.25) -> str:
        if self._retriever is None:
            print("Building retriever")
            self._build_retriever()

        query_tokens = bm25s.tokenize(query, stemmer=self._stemmer)
        results, scores = self._retriever.retrieve(
            query_tokens, k=min(10, len(self._tools))
        )
        for i in range(results.shape[1]):
            doc, score = results[0, i], scores[0, i]
            print(f"Rank {i + 1} (score: {score:.2f}): {doc}")
            if score >= score_threshold:
                return self._tools[int(doc)]
        return None
