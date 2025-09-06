import lancedb
from typing import TypedDict
import pandas as pd
from zerozen.memory.embedding import Chat


class DBManager:
    def __init__(self):
        uri = "zerozen/messages"
        self._db = lancedb.connect(uri)

    def open_or_create_table(self) -> lancedb.table.Table:
        try:
            tbl = self._db.open_table("messages")
            # Check if the table has the expected schema
            schema = tbl.schema
            expected_fields = {"user", "agent", "text", "embedding"}
            actual_fields = {field.name for field in schema}
            if not expected_fields.issubset(actual_fields):
                # Schema mismatch, recreate the table
                self._db.drop_table("messages")
                tbl = self._db.create_table(
                    "messages",
                    schema=Chat,
                )
        except Exception:
            tbl = self._db.create_table(
                "messages",
                schema=Chat,
            )
        return tbl

    def table_names(self):
        return self._db.table_names()


class ChatType(TypedDict):
    user: str
    agent: str
    text: str


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

    def __init__(self):
        self.db = DBManager()
        self.tbl = self.db.open_or_create_table()
        self._messages = []

    @property
    def messages(self):
        return self._messages

    def _process_dict_msg(self, message: dict) -> str:
        if "user" in message and (
            "assistant" in message or "system" in message or "agent" in message
        ):
            return f"<user>{message['user']}</user>\n<assistant>{message['assistant']}</assistant>\n\n"
        else:
            raise ValueError("Invalid message")

    def _process_list_msg(self, message: list[dict]) -> str:
        dict_msg = {"user": message[0]["content"], "assistant": message[1]["content"]}
        return self._process_dict_msg(dict_msg)

    def add(self, message: ChatType) -> None:
        if isinstance(message, dict):
            text = self._process_dict_msg(message)
            # Create a dictionary instead of Chat instance to let LanceDB handle embeddings
            chat_data = {
                "user": message["user"],
                "agent": message["assistant"],
                "text": text,
            }
            self.tbl.add([chat_data])

        else:
            raise ValueError("Invalid message")

    def search(self, query: str, limit: int = 10) -> pd.DataFrame:
        return self.tbl.search(query).limit(limit).to_pandas()

    def get_full_conversation(self) -> str:
        return self.tbl.to_pandas()
