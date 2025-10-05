from agentor.memory.api import DBManager, Memory

from lancedb.embeddings import register, TextEmbeddingFunction
import numpy as np
from cachetools.func import cached
import os
from unittest.mock import patch


@register("sentence-transformers")
class DummyEmbeddings(TextEmbeddingFunction):
    name: str = "dummy"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ndims = 384

    def generate_embeddings(self, texts):
        return np.random.rand(len(texts), self._ndims).tolist()

    def ndims(self):
        return self._ndims

    @cached(cache={})
    def _embedding_model(self):
        return None


def test_db(tmp_path):
    db = DBManager(tmp_path / "memory")
    tbl = db.open_or_create_table("conversations")
    assert db.table_names() == ["conversations"]
    assert tbl is not None
    assert len(os.listdir(tmp_path)) > 0


@patch("lancedb.embeddings.get_registry", return_value={"dummy": DummyEmbeddings})
def test_memory(mock_get_registry, tmp_path):
    mem = Memory(tmp_path / "memory")
    mem.add(user="How many 'r's in apples?", agent="there are 0 'r's in apples")
    assert mem.search("apple", limit=1) is not None
