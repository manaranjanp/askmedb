"""Custom exceptions for AskDB."""


class AskDBError(Exception):
    """Base exception for AskDB."""
    pass


class SQLExecutionError(AskDBError):
    """Raised when SQL execution fails."""

    def __init__(self, message: str, sql: str = ""):
        self.sql = sql
        super().__init__(message)


class LLMError(AskDBError):
    """Raised when LLM call fails."""
    pass


class SchemaError(AskDBError):
    """Raised when schema loading or validation fails."""
    pass


class ConfigError(AskDBError):
    """Raised when configuration is invalid."""
    pass
