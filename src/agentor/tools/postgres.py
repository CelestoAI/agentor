import sys
from types import ModuleType
from typing import Any, List, Optional

from agentor.tools.base import BaseTool, capability

try:
    import psycopg2
except ImportError:
    psycopg2 = ModuleType("psycopg2")

    class Error(Exception):
        """Raised when psycopg2 dependency is not installed."""

    def connect(*args, **kwargs):
        raise Error(
            "PostgreSQL dependency is missing. Please install it with `pip install agentor[postgres]`."
        )

    psycopg2.Error = Error  # type: ignore[attr-defined]
    psycopg2.connect = connect  # type: ignore[attr-defined]
    sys.modules["psycopg2"] = psycopg2


class PostgreSQLTool(BaseTool):
    name = "postgresql"
    description = "Execute SQL queries on a PostgreSQL database."

    def __init__(self, dsn: str, api_key: Optional[str] = None):
        if psycopg2 is None:
            raise ImportError(
                "PostgreSQL dependency is missing. Please install it with `pip install agentor[postgres]`."
            )
        super().__init__(api_key)
        self.dsn = dsn

    @capability
    def execute_query(self, query: str, params: Optional[List[Any]] = None) -> str:
        """Execute a SQL query."""
        conn = None
        try:
            conn = psycopg2.connect(self.dsn)
            cur = conn.cursor()
            cur.execute(query, params)

            if query.strip().upper().startswith("SELECT"):
                results = cur.fetchall()
                conn.commit()
                return str(results)
            else:
                conn.commit()
                return "Query executed successfully."

        except psycopg2.Error as e:
            return f"Database error: {e}"
        except Exception as e:
            return f"Error executing query: {str(e)}"
        finally:
            if conn:
                conn.close()

    @capability
    def list_tables(self) -> str:
        """List all tables in the public schema."""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """
        return self.execute_query(query)
