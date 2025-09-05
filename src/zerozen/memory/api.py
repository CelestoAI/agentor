import lancedb
import pandas as pd
import pyarrow as pa


class DBManager:
    def __init__(self):
        uri = "zerozen/messages"
        self._db = lancedb.connect(uri)

    def open_or_create_table(self):
        try:
            tbl = self._db.open_table("messages")
        except Exception:
            tbl = self._db.create_table(
                "messages",
                schema=pa.schema(
                    [
                        pa.field("role", pa.string()),
                        pa.field("content", pa.string()),
                    ]
                ),
            )
        return tbl

    def table_names(self):
        return self._db.table_names()


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

    def _process_dict_msg(self, message: dict):
        if "user" in message and (
            "assistant" in message or "system" in message or "agent" in message
        ):
            return f"<user>{message['user']}</user>\n<assistant>{message['assistant']}</assistant>\n\n"
        else:
            raise ValueError("Invalid message")

    def _process_list_msg(self, message: list[dict]):
        dict_msg = {"user": message[0]["content"], "assistant": message[1]["content"]}
        return self._process_dict_msg(dict_msg)

    def add(self, message: list[dict] | str | dict):
        if isinstance(message, dict):
            self.messages.append(self._process_dict_msg(message))

        elif isinstance(message, str):
            self.messages.append(message)

        elif isinstance(message, list):
            self.messages.append(self._process_list_msg(message))

        else:
            raise ValueError("Invalid message")

    def search(self, query: str, limit: int = 10) -> pd.DataFrame:
        return self.tbl.search(query).limit(limit).to_pandas()

    def get_full_conversation(self):
        return "\n".join(self.messages)
