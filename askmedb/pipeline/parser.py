"""Parse LLM responses to extract SQL queries and reasoning."""

import re


def parse_sql_response(text: str) -> tuple[str, str]:
    """Extract SQL query and reasoning from the LLM's response.

    Expected format:
        REASONING: <step-by-step reasoning>
        SQL: ```sql
        <query>
        ```

    Returns:
        (sql_query, reasoning) tuple. sql_query may be empty if none found.
    """
    reasoning = ""
    sql = ""

    # Try to extract REASONING section
    reasoning_match = re.search(
        r"REASONING:\s*(.*?)(?=\nSQL:|```sql|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    # Try to extract SQL from "SQL:" marker
    sql_match = re.search(
        r"SQL:\s*```sql\s*(.*?)\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not sql_match:
        sql_match = re.search(
            r"SQL:\s*(.*?)(?:\n\n|$)",
            text,
            re.DOTALL | re.IGNORECASE,
        )

    # Try code block fallback
    if not sql_match:
        sql_match = re.search(
            r"```sql\s*(.*?)\s*```",
            text,
            re.DOTALL,
        )

    # Try generic code block
    if not sql_match:
        sql_match = re.search(
            r"```\s*(SELECT.*?)\s*```",
            text,
            re.DOTALL | re.IGNORECASE,
        )

    if sql_match:
        sql = sql_match.group(1).strip()
        sql = sql.rstrip(";").strip()

    # If no structured reasoning found, use everything before the SQL
    if not reasoning and sql:
        before_sql = (
            text[:text.lower().find(sql.lower()[:20])]
            if sql[:20].lower() in text.lower()
            else text
        )
        reasoning = before_sql.strip()

    return sql, reasoning


def parse_answer_response(text: str) -> str:
    """Clean up the answer response from the LLM."""
    return text.strip()
