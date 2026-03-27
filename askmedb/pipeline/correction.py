"""Self-correction logic: retry failed queries and accumulate learnings."""

import json
import os
import tempfile
import threading
from datetime import datetime
from typing import Optional

from .parser import parse_sql_response
from ..llm.base import BaseLLMProvider
from ..context.prompts import PromptTemplate


class SelfCorrector:
    """Handles SQL self-correction and learning accumulation.

    Thread-safe. Learnings are protected by a lock and persisted
    atomically (temp file + rename) to prevent corruption.

    Args:
        llm: LLM provider for generating corrections.
        prompt_template: Prompt template for building correction prompts.
        learnings_path: Optional file path to persist learnings. None = in-memory only.
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        prompt_template: PromptTemplate,
        learnings_path: Optional[str] = None,
        sql_temperature: float = 0.0,
        sql_max_tokens: int = 2048,
    ):
        self.llm = llm
        self.prompt_template = prompt_template
        self.learnings_path = learnings_path
        self.sql_temperature = sql_temperature
        self.sql_max_tokens = sql_max_tokens
        self._learnings: list[dict] = []
        self._lock = threading.Lock()
        if learnings_path:
            self._load_learnings()

    def _load_learnings(self):
        """Load learnings from file if it exists."""
        if self.learnings_path and os.path.exists(self.learnings_path):
            try:
                with open(self.learnings_path) as f:
                    self._learnings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._learnings = []

    @property
    def learnings(self) -> list[dict]:
        """Get a copy of the current learnings list."""
        with self._lock:
            return list(self._learnings)

    def attempt_correction(
        self,
        error: str,
        original_sql: str,
        messages: list[dict],
    ) -> tuple[str, str]:
        """Ask the LLM to fix a failed SQL query.

        Args:
            error: The error message from the failed query.
            original_sql: The SQL that failed.
            messages: The full message history for context.

        Returns:
            (corrected_sql, reasoning) tuple.
        """
        correction_prompt = self.prompt_template.build_correction_prompt(
            original_sql=original_sql,
            error=error,
        )

        correction_messages = messages + [{"role": "user", "content": correction_prompt}]
        response = self.llm.generate(
            correction_messages,
            temperature=self.sql_temperature,
            max_tokens=self.sql_max_tokens,
        )
        return parse_sql_response(response)

    def save_learning(
        self,
        question: str,
        error: str,
        wrong_sql: str,
        corrected_sql: str,
        lesson: str,
    ):
        """Save a learning from a successful self-correction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "error": error,
            "wrong_sql": wrong_sql,
            "corrected_sql": corrected_sql,
            "lesson": lesson,
        }

        with self._lock:
            self._learnings.append(entry)

            if self.learnings_path:
                self._persist_learnings()

    def _persist_learnings(self):
        """Write learnings to file atomically. Must be called with lock held."""
        try:
            dir_name = os.path.dirname(self.learnings_path) or "."
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self._learnings, f, indent=2)
                os.replace(tmp_path, self.learnings_path)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except IOError:
            pass
