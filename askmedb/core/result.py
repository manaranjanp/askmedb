"""Query result dataclass for AskMeDB."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QueryResult:
    """Result returned by AskMeDBEngine.ask().

    Attributes:
        question: The original natural-language question.
        sql: The generated (or corrected) SQL query.
        columns: Column names from the query result.
        rows: Row tuples from the query result.
        answer: Human-readable answer synthesized by the LLM.
        reasoning: LLM's reasoning about how it built the query.
        correction_attempts: Number of self-correction attempts needed.
        warnings: Heuristic warnings about the results.
        error: Error message if the query ultimately failed.
    """

    question: str
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    answer: str = ""
    reasoning: str = ""
    correction_attempts: int = 0
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether the query executed successfully."""
        return self.error is None

    @property
    def row_count(self) -> int:
        """Number of result rows."""
        return len(self.rows)

    def to_dataframe(self):
        """Convert results to a pandas DataFrame.

        Requires pandas to be installed.
        """
        import pandas as pd
        return pd.DataFrame(self.rows, columns=self.columns)

    def to_dicts(self) -> list[dict]:
        """Convert results to a list of dictionaries."""
        return [dict(zip(self.columns, row)) for row in self.rows]
