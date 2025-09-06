import lancedb
from typing import TypedDict
import pandas as pd
from zerozen.memory.embedding import Chat


class DBManager:
    def __init__(self, uri: str = "zerozen/messages"):
        self.uri = uri
        self._db = lancedb.connect(self.uri)

    def open_or_create_table(self, table_name: str = "messages") -> lancedb.table.Table:
        try:
            tbl = self._db.open_table(table_name)
            # Check if the table has the expected schema
            schema = tbl.schema
            expected_fields = set(Chat.__fields__.keys())
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
                schema=Chat,
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
    memory = Memory()

    response = client.responses.create(
        model="gpt-5",
        input="Hello, how are you?",
    )
    print(response.output)

    memory.add_message(response.output)
    """

    def __init__(
        self, db_uri: str = "zerozen/messages", table_name: str = "conversations"
    ):
        self.db = DBManager(db_uri)
        self.tbl = self.db.open_or_create_table(table_name)

    def add(
        self, conversation: ChatType | None = None, user: str = None, agent: str = None
    ) -> None:
        if conversation is not None:
            user = conversation["user"]
            agent = conversation["agent"]
        else:
            if user is None:
                raise ValueError("User must be a string")
            if agent is None:
                raise ValueError("Agent must be a string")

        text = f"<user>{user}</user>\n<assistant>{agent}</assistant>\n\n"
        chat_data = {
            "user": user,
            "agent": agent,
            "text": text,
        }
        self.tbl.add([chat_data])

    def search(self, query: str, limit: int = 10) -> pd.DataFrame:
        return self.tbl.search(query).limit(limit).to_pandas()

    def get_full_conversation(self) -> str:
        return self.tbl.to_pandas()
