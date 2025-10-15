from typing import TypedDict

import lancedb
import pandas as pd
from typeguard import typechecked


import pyarrow as pa
from lancedb.embeddings import (
    EmbeddingFunctionConfig,
    TextEmbeddingFunction,
    get_registry,
    register,
)
from lancedb.schema import vector as vector_type


DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIM = 384
SOURCE_COLUMN = "text"
VECTOR_COLUMN = "embedding"


@register("sentence-transformers")
class SentenceTransformerEmbeddings(TextEmbeddingFunction):
    name: str = "all-MiniLM-L6-v2"

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


def get_embedding(text: str, name: str = DEFAULT_MODEL_NAME):
    func = get_registry().get("sentence-transformers").create(name=name)
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
        function=get_registry().get("sentence-transformers").create(name=name),
    )


class _VectorDBManager:
    def __init__(self, uri: str):
        self.uri = uri
        self._db = lancedb.connect(self.uri)

    @typechecked
    def open_or_create_table(self, table_name: str) -> lancedb.table.Table:
        tbl = self._db.create_table(
            table_name,
            schema=get_chat_schema(),
            embedding_functions=[get_embedding_config()],
        )
        return tbl

    def table_names(self):
        return self._db.table_names()


class ChatType(TypedDict):
    user: str
    agent: str


class Memory:
    """
    Example:


    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.responses.create(
        model="gpt-5",
        input="how many 'r's in strawberries?",
    )

    memory = Memory()
    memory.add(user="how many 'r's in strawberries?", agent=response.output)
    memory.search("strawberries")
    """

    def __init__(
        self, db_uri: str = ".agentor/memory", table_name: str = "conversations"
    ):
        self.db = _VectorDBManager(db_uri)
        self.tbl = self.db.open_or_create_table(table_name)

    @typechecked
    def add(
        self,
        conversation: ChatType | None = None,
        user: str | None = None,
        agent: str | None = None,
    ) -> None:
        if conversation is not None:
            user = conversation["user"]
            agent = conversation["agent"]
        else:
            if user is None:
                raise ValueError("User must be a string")
            if agent is None:
                raise ValueError("Agent must be a string")

        text = f"<user> {user} </user>\n<assistant> {agent} </assistant>\n\n"
        chat_data = {
            "user": user,
            "agent": agent,
            SOURCE_COLUMN: text,
        }
        self.tbl.add([chat_data])

    @typechecked
    def search(self, query: str, limit: int = 10) -> pd.DataFrame:
        return self.tbl.search(query).limit(limit).to_pandas()

    def get_full_conversation(self) -> pd.DataFrame:
        return self.tbl.to_pandas()
