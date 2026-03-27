"""SQLite database connector."""

import os
import sqlite3

from .base import BaseDBConnector

_ENV_DB_PATH = "SQLITE_DB_PATH"


class SQLiteConnector(BaseDBConnector):
    """SQLite database connector.

    The database file path is read from the ``SQLITE_DB_PATH`` environment
    variable by default.  Pass ``db_path`` explicitly to override it.

    SQLite is an embedded, file-based database — it has no server, no user
    accounts, and no password.  The file path is the only required value.

    Required environment variable
    --------------------------------
    ``SQLITE_DB_PATH``
        Path to the SQLite database file, e.g. ``/data/mydb.sqlite``.
        Use the special value ``:memory:`` for a temporary in-memory database.

    Example ``.env`` file::

        SQLITE_DB_PATH=/data/mydb.sqlite

    Example usage::

        # Path from env var
        from askmedb.db.sqlite import SQLiteConnector
        db = SQLiteConnector()

        # Explicit path (overrides env var)
        db = SQLiteConnector(db_path="/data/mydb.sqlite")

        # In-memory database (testing / PandasConnector internal use)
        db = SQLiteConnector(db_path=":memory:")
    """

    def __init__(self, db_path: str | None = None, read_only: bool = False):
        resolved = db_path or os.environ.get(_ENV_DB_PATH)
        if not resolved:
            raise ValueError(
                f"SQLite database path is required. "
                f"Set the {_ENV_DB_PATH!r} environment variable or pass db_path=.\n"
                f"Example: {_ENV_DB_PATH}=/data/mydb.sqlite"
            )
        self.db_path = resolved
        self.read_only = read_only

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query against the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            if self.read_only:
                conn.execute("PRAGMA query_only = ON")
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return columns, rows
        finally:
            conn.close()

    def get_dialect(self) -> str:
        return "sqlite"
