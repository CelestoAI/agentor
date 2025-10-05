from typing import TypedDict

import lancedb
import pandas as pd
from typeguard import typechecked

from agentor.memory.embedding import (
    SOURCE_COLUMN,
    get_chat_schema,
    get_embedding_config,
)

CHAT_SCHEMA = get_chat_schema()
CHAT_FIELD_NAMES = set(CHAT_SCHEMA.names)


class DBManager:
    def __init__(self, uri: str):
        self.uri = uri
        self._db = lancedb.connect(self.uri)

    @typechecked
    def open_or_create_table(self, table_name: str) -> lancedb.table.Table:
        try:
            tbl = self._db.open_table(table_name)
            # Check if the table has the expected schema
            schema = tbl.schema
            expected_fields = CHAT_FIELD_NAMES
            actual_fields = {field.name for field in schema}
            if not expected_fields.issubset(actual_fields):
                # Schema mismatch, recreate the table
                raise ValueError(
                    f"Schema mismatch for table {table_name}. Expected fields: {expected_fields}, Actual fields: {actual_fields}\n"
                    "Please delete the table and try again."
                )
        except Exception as e:
            print(e)
            tbl = self._db.create_table(
                table_name,
                schema=CHAT_SCHEMA,
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
        self, db_uri: str = ".zendata/memory", table_name: str = "conversations"
    ):
        self.db = DBManager(db_uri)
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
