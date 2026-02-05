"""End-to-end Agentor example: PostgreSQLTool.

Requirements:
    pip install "agentor[postgres]"

Environment:
    export POSTGRES_DSN=postgresql://user:password@host:5432/dbname
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import PostgreSQLTool


def main() -> None:
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise ValueError("POSTGRES_DSN is required")

    agent = Agentor(
        name="PostgreSQL Agent",
        model="gpt-5-mini",
        tools=[PostgreSQLTool(dsn=dsn)],
        instructions="Use PostgreSQL tool capabilities for database queries.",
    )

    result = agent.run(
        "Use list_tables and return the table names in the public schema."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
