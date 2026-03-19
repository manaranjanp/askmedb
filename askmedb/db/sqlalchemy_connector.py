"""SQLAlchemy database connector for multi-database support."""

from .base import BaseDBConnector

try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class SQLAlchemyConnector(BaseDBConnector):
    """Database connector using SQLAlchemy.

    Supports PostgreSQL, MySQL, SQLite, and any other SQLAlchemy-compatible database.

    Args:
        connection_string: SQLAlchemy connection URL
            (e.g. "postgresql://user:pass@localhost/mydb").
        dialect: Override the auto-detected dialect name for prompt hints.
    """

    def __init__(self, connection_string: str, dialect: str | None = None):
        if not HAS_SQLALCHEMY:
            raise ImportError(
                "SQLAlchemy is required for SQLAlchemyConnector. "
                "Install it with: pip install askmedb[sql]"
            )
        self.engine = create_engine(connection_string)
        self._dialect = dialect or self.engine.dialect.name

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query using SQLAlchemy."""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys()) if result.returns_rows else []
            rows = [tuple(row) for row in result.fetchall()] if result.returns_rows else []
            return columns, rows

    def get_dialect(self) -> str:
        return self._dialect

    def close(self):
        self.engine.dispose()
