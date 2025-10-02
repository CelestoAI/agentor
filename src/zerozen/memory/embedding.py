from functools import lru_cache

import pyarrow as pa
from lancedb.embeddings import (
    EmbeddingFunctionConfig,
    TextEmbeddingFunction,
    get_registry,
    register,
)
from lancedb.schema import vector as vector_type
from typeguard import typechecked

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIM = 384
SOURCE_COLUMN = "text"
VECTOR_COLUMN = "embedding"


@register("sentence-transformers")
class SentenceTransformerEmbeddings(TextEmbeddingFunction):
    name: str = DEFAULT_MODEL_NAME

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ndims = DEFAULT_EMBEDDING_DIM
        self._model = None

    @typechecked
    def generate_embeddings(self, texts: list[str]):
        return self._embedding_model().encode(texts).tolist()

    def ndims(self):
        return self._ndims

    def _embedding_model(self):
        import sentence_transformers

        if self._model is None:
            self._model = sentence_transformers.SentenceTransformer(self.name)
        return self._model


@lru_cache(maxsize=8)
def _create_embedding_func(name: str):
    return get_registry().get("sentence-transformers").create(name=name)


def get_embedding_func(name: str = DEFAULT_MODEL_NAME):
    return _create_embedding_func(name)


def get_embedding(text: str, name: str = DEFAULT_MODEL_NAME):
    func = get_embedding_func(name)
    return func.embed_query(text)


def get_chat_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("user", pa.string()),
            pa.field("agent", pa.string()),
            pa.field(SOURCE_COLUMN, pa.string()),
            pa.field(VECTOR_COLUMN, vector_type(DEFAULT_EMBEDDING_DIM)),
        ]
    )


def get_embedding_config(name: str = DEFAULT_MODEL_NAME) -> EmbeddingFunctionConfig:
    return EmbeddingFunctionConfig(
        vector_column=VECTOR_COLUMN,
        source_column=SOURCE_COLUMN,
        function=get_embedding_func(name),
    )
