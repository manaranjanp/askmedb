"""Result validation and formatting utilities."""

import re

from ..core.exceptions import SQLExecutionError

# SQL statements that are allowed in read-only mode
_READ_ONLY_PREFIXES = ("select", "with", "explain", "pragma")

# Pattern to strip SQL comments (both -- line and /* block */ styles)
_COMMENT_PATTERN = re.compile(
    r"--[^\n]*|/\*.*?\*/",
    re.DOTALL,
)


def enforce_read_only(sql: str) -> None:
    """Raise SQLExecutionError if the SQL statement is not a read-only query.

    Only SELECT, WITH, EXPLAIN, and PRAGMA statements are allowed.
    """
    # Strip comments and whitespace to find the first meaningful token
    cleaned = _COMMENT_PATTERN.sub("", sql).strip()
    if not cleaned:
        raise SQLExecutionError("Empty SQL query.", sql=sql)

    first_token = cleaned.split()[0].lower()
    if first_token not in _READ_ONLY_PREFIXES:
        raise SQLExecutionError(
            f"Read-only mode is enabled. Only SELECT queries are allowed, "
            f"but got a {first_token.upper()} statement.",
            sql=sql,
        )


def validate_results(columns: list[str], rows: list[tuple]) -> list[str]:
    """Run heuristic checks on query results and return warnings.

    Returns:
        List of warning strings. Empty list means no issues detected.
    """
    warnings = []

    if not rows:
        warnings.append("Query returned 0 rows. The filters may be too restrictive.")
        return warnings

    if len(rows) == 1 and len(columns) == 1:
        val = rows[0][0]
        if val is None:
            warnings.append("Result is NULL. Check if the aggregation has matching data.")
        elif isinstance(val, (int, float)) and val < 0:
            warnings.append(f"Result is negative ({val}). This may indicate a calculation error.")

    if len(rows) > 10000:
        warnings.append(
            f"Query returned {len(rows)} rows. Consider adding LIMIT or more specific filters."
        )

    return warnings


def format_results_for_llm(
    columns: list[str], rows: list[tuple], max_rows: int = 30
) -> str:
    """Format query results as a text table for the LLM to read.

    Args:
        columns: Column names.
        rows: Result rows.
        max_rows: Maximum rows to include in the output.

    Returns:
        Formatted text table string.
    """
    if not rows:
        return "(no rows returned)"

    lines = [" | ".join(columns)]
    lines.append("-" * len(lines[0]))
    for row in rows[:max_rows]:
        lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)
