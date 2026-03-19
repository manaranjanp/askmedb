"""AskDB — A library for building natural-language database query agents.

Quick start:
    >>> from askdb import AskDBEngine, SQLiteConnector
    >>> engine = AskDBEngine(
    ...     db=SQLiteConnector("my_database.db"),
    ...     schema={"tables": [...]},
    ... )
    >>> result = engine.ask("How many rows are in the users table?")
    >>> print(result.answer)
"""

from .core.config import AskDBConfig
from .core.result import QueryResult
from .core.engine import AskDBEngine
from .db.base import BaseDBConnector
from .db.sqlite import SQLiteConnector
from .llm.base import BaseLLMProvider
from .llm.litellm_provider import LiteLLMProvider
from .context.schema import (
    SchemaProvider,
    JSONSchemaProvider,
    DictSchemaProvider,
    AutoSchemaProvider,
)
from .context.builder import ContextBuilder
from .context.prompts import PromptTemplate, DIALECT_HINTS
from .pipeline.conversation import ConversationManager
from .pipeline.parser import parse_sql_response, parse_answer_response
from .pipeline.validation import validate_results, format_results_for_llm
from .core.exceptions import AskDBError, SQLExecutionError, LLMError, SchemaError, ConfigError

__version__ = "0.1.0"

__all__ = [
    # Core
    "AskDBEngine",
    "AskDBConfig",
    "QueryResult",
    # Database
    "BaseDBConnector",
    "SQLiteConnector",
    # LLM
    "BaseLLMProvider",
    "LiteLLMProvider",
    # Context
    "SchemaProvider",
    "JSONSchemaProvider",
    "DictSchemaProvider",
    "AutoSchemaProvider",
    "ContextBuilder",
    "PromptTemplate",
    "DIALECT_HINTS",
    # Pipeline
    "ConversationManager",
    "parse_sql_response",
    "parse_answer_response",
    "validate_results",
    "format_results_for_llm",
    # Exceptions
    "AskDBError",
    "SQLExecutionError",
    "LLMError",
    "SchemaError",
    "ConfigError",
]
