"""SQLite database connector."""

import sqlite3
from .base import BaseDBConnector


class SQLiteConnector(BaseDBConnector):
    """SQLite database connector.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query against the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return columns, rows
        finally:
            conn.close()

    def get_dialect(self) -> str:
        return "sqlite"
