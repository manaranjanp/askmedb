"""Abstract base class for database connectors."""

from abc import ABC, abstractmethod


class BaseDBConnector(ABC):
    """Abstract base for database connections.

    Implement this interface to support any database backend.
    """

    @abstractmethod
    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query and return results.

        Args:
            sql: SQL query string to execute.

        Returns:
            Tuple of (column_names, rows).

        Raises:
            Exception on SQL execution failure.
        """
        ...

    @abstractmethod
    def get_dialect(self) -> str:
        """Return the SQL dialect name (e.g. 'sqlite', 'postgresql', 'mysql').

        Used by the prompt builder to include dialect-specific instructions.
        """
        ...

    def close(self):
        """Close the database connection. Override if cleanup is needed."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
