"""SQLAlchemy database connector for multi-database support."""

import os

from .base import BaseDBConnector

try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

_ENV_DATABASE_URL = "DATABASE_URL"

_URL_EXAMPLES = """
    PostgreSQL : DATABASE_URL=postgresql://user:password@host:5432/dbname
    MySQL      : DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname
    SQLite     : DATABASE_URL=sqlite:///./local.db
    MS SQL     : DATABASE_URL=mssql+pyodbc://user:password@host/dbname?driver=ODBC+Driver+17+for+SQL+Server
    Oracle     : DATABASE_URL=oracle+cx_oracle://user:password@host:1521/service
"""


class SQLAlchemyConnector(BaseDBConnector):
    """Database connector using SQLAlchemy.

    Supports PostgreSQL, MySQL, SQLite, MS SQL Server, Oracle, and any other
    SQLAlchemy-compatible database.

    The connection string is read from the ``DATABASE_URL`` environment variable
    by default — this is the standard convention used by most cloud platforms
    (Heroku, Railway, Render) and frameworks (Django, SQLAlchemy docs).
    Pass ``connection_string`` explicitly to override it.

    .. warning::
        Never hardcode credentials in the connection string in source code.
        Always use the environment variable or a secrets manager.

    Required environment variable
    --------------------------------
    ``DATABASE_URL``
        A SQLAlchemy connection URL containing the driver, credentials, host,
        port, and database name.  Format varies by database — see examples below.

    Optional
    --------------------------------
    ``dialect``  (constructor argument only)
        Override the auto-detected dialect name used for LLM prompt hints.
        Useful when the detected name doesn't match a known hint key.

    Example ``.env`` file::

        # PostgreSQL
        DATABASE_URL=postgresql://alice:s3cr3t@prod-db.internal:5432/analytics

        # MySQL
        DATABASE_URL=mysql+pymysql://root:pass@localhost:3306/mydb

        # SQLite (relative path)
        DATABASE_URL=sqlite:///./local.db

    Example usage::

        # Connection string from env var
        from askmedb.db.sqlalchemy_connector import SQLAlchemyConnector
        db = SQLAlchemyConnector()

        # Explicit connection string (overrides env var)
        db = SQLAlchemyConnector("postgresql://alice:s3cr3t@localhost/analytics")

        # Override dialect hint (e.g. force postgresql hints for a pg-compatible DB)
        db = SQLAlchemyConnector(dialect="postgresql")
    """

    def __init__(self, connection_string: str | None = None, dialect: str | None = None):
        if not HAS_SQLALCHEMY:
            raise ImportError(
                "SQLAlchemy is required for SQLAlchemyConnector. "
                "Install it with: pip install askmedb[sql]"
            )

        resolved = connection_string or os.environ.get(_ENV_DATABASE_URL)
        if not resolved:
            raise ValueError(
                f"A database connection string is required. "
                f"Set the {_ENV_DATABASE_URL!r} environment variable or pass connection_string=.\n"
                f"Examples by database type:{_URL_EXAMPLES}"
            )

        self.engine = create_engine(resolved)
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
