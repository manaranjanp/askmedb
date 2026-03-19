"""Custom exceptions for AskMeDB."""


class AskMeDBError(Exception):
    """Base exception for AskMeDB."""
    pass


class SQLExecutionError(AskMeDBError):
    """Raised when SQL execution fails."""

    def __init__(self, message: str, sql: str = ""):
        self.sql = sql
        super().__init__(message)


class LLMError(AskMeDBError):
    """Raised when LLM call fails."""
    pass


class SchemaError(AskMeDBError):
    """Raised when schema loading or validation fails."""
    pass


class ConfigError(AskMeDBError):
    """Raised when configuration is invalid."""
    pass
