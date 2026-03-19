"""Configuration dataclass for AskDB."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AskDBConfig:
    """Configuration for an AskDB engine instance.

    Attributes:
        model: LLM model string in LiteLLM format (e.g. "anthropic/claude-haiku-4-5-20251001").
        sql_temperature: Temperature for SQL generation (0.0 = deterministic).
        answer_temperature: Temperature for answer synthesis.
        sql_max_tokens: Max tokens for SQL generation response.
        answer_max_tokens: Max tokens for answer synthesis response.
        max_retries: Max LLM API call retries with exponential backoff.
        max_correction_attempts: Max self-correction attempts for failed SQL.
        max_conversation_turns: Max conversation turns to keep in history.
        max_result_rows: Max rows to include in LLM context for answer synthesis.
        system_prompt_prefix: Text prepended to the generated system prompt.
        system_prompt_override: If set, replaces the entire generated system prompt.
        enable_learnings: Whether to persist and use self-correction learnings.
        learnings_path: File path for persisting learnings. None = in-memory only.
    """

    model: str = "anthropic/claude-haiku-4-5-20251001"
    sql_temperature: float = 0.0
    answer_temperature: float = 0.3
    sql_max_tokens: int = 2048
    answer_max_tokens: int = 4096
    max_retries: int = 3
    max_correction_attempts: int = 3
    max_conversation_turns: int = 10
    max_result_rows: int = 30
    system_prompt_prefix: Optional[str] = None
    system_prompt_override: Optional[str] = None
    enable_learnings: bool = True
    learnings_path: Optional[str] = None
