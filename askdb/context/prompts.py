"""Prompt templates for AskDB."""

DIALECT_HINTS = {
    "sqlite": (
        "5. For date operations, use SQLite functions: strftime(), date(), julianday(). "
        "Do NOT use DATE_TRUNC, EXTRACT, DATEDIFF, or EPOCH.\n"
        "6. For date arithmetic (time differences), use: julianday(date1) - julianday(date2) "
        "(gives days). Multiply by 24 for hours.\n"
        "7. For recent periods, use: date('now', '-N months') or date('now', '-N days')."
    ),
    "postgresql": (
        "5. For date operations, use PostgreSQL functions: DATE_TRUNC(), EXTRACT(), AGE(). "
        "Do NOT use SQLite-specific functions like julianday() or strftime().\n"
        "6. For date arithmetic, use interval arithmetic: date1 - date2, "
        "or EXTRACT(EPOCH FROM age(date1, date2)).\n"
        "7. For recent periods, use: CURRENT_DATE - INTERVAL 'N months'."
    ),
    "mysql": (
        "5. For date operations, use MySQL functions: DATE_FORMAT(), YEAR(), MONTH(), "
        "DATEDIFF(), TIMESTAMPDIFF().\n"
        "6. For date arithmetic, use: DATEDIFF(date1, date2) for days, "
        "TIMESTAMPDIFF(HOUR, date1, date2) for hours.\n"
        "7. For recent periods, use: DATE_SUB(CURDATE(), INTERVAL N MONTH)."
    ),
}

# Fallback for unknown dialects
_DEFAULT_DIALECT_HINT = (
    "5. Use standard SQL date functions appropriate for this database.\n"
    "6. For date arithmetic, use functions appropriate for this database dialect.\n"
    "7. For recent periods, use date functions appropriate for this database dialect."
)


class PromptTemplate:
    """Customizable prompt template for AskDB.

    The default template produces the same output as the original CloudMetrics
    agent but with configurable sections.

    Args:
        agent_description: Description of the agent's role.
        dialect: SQL dialect name for dialect-specific hints.
        custom_instructions: Additional instructions appended to the prompt.
    """

    def __init__(
        self,
        agent_description: str = "You are a data analyst agent. You answer natural language questions by generating SQL queries.",
        dialect: str = "sqlite",
        custom_instructions: str = "",
    ):
        self.agent_description = agent_description
        self.dialect = dialect
        self.custom_instructions = custom_instructions

    def build(
        self,
        schema_text: str,
        business_rules_text: str = "",
        query_patterns_text: str = "",
        learnings_text: str = "",
    ) -> str:
        """Build the complete system prompt.

        Args:
            schema_text: Formatted schema string.
            business_rules_text: Formatted business rules string.
            query_patterns_text: Formatted query patterns/examples string.
            learnings_text: Formatted learnings string.

        Returns:
            Complete system prompt string.
        """
        dialect_hint = DIALECT_HINTS.get(self.dialect, _DEFAULT_DIALECT_HINT)
        dialect_label = self.dialect.upper() if self.dialect else "SQL"

        prompt = f"""{self.agent_description}
You generate {dialect_label}-compatible SQL queries.

== DATABASE SCHEMA ==
{schema_text}
"""

        if business_rules_text:
            prompt += f"\n== BUSINESS RULES AND METRIC DEFINITIONS ==\n{business_rules_text}\n"

        if query_patterns_text:
            prompt += f"\n== {query_patterns_text}\n"

        if learnings_text:
            prompt += f"\n== {learnings_text}\n"

        prompt += f"""
== INSTRUCTIONS ==
1. Analyze the user's question carefully.
2. Generate a valid {dialect_label} SQL query to answer it.
3. Return your response in this exact format:
   REASONING: <your step-by-step reasoning about which tables, joins, and filters to use>
   SQL: ```sql
   <your SQL query here>
   ```
4. Use ONLY tables and columns from the schema above. Double-check column names.
{dialect_hint}
8. Always apply appropriate WHERE clauses based on business rules (e.g., status filters).
9. If the question is ambiguous, state your assumptions in the REASONING section.
10. If this is a follow-up question, use context from previous messages to understand what "it", "that", "those" refer to.
"""

        if self.custom_instructions:
            prompt += f"\n{self.custom_instructions}\n"

        return prompt

    def build_correction_prompt(
        self,
        original_sql: str,
        error: str,
    ) -> str:
        """Build a self-correction prompt for a failed SQL query."""
        dialect_hint = DIALECT_HINTS.get(self.dialect, _DEFAULT_DIALECT_HINT)

        return f"""The previous SQL query failed with an error. Fix it.

ORIGINAL SQL:
```sql
{original_sql}
```

ERROR:
{error}

IMPORTANT REMINDERS:
- This is a {self.dialect} database.
- Double-check all column names against the schema.
- Ensure all table aliases are consistent.

Please provide the corrected query in the same format:
REASONING: <what went wrong and how you fixed it>
SQL: ```sql
<corrected SQL>
```"""

    def build_answer_prompt(self, question: str) -> str:
        """Build the prompt for answer synthesis from SQL results."""
        return (
            f'Based on the SQL results above, provide a clear, concise answer to '
            f'the original question: "{question}"\n\n'
            f'Include key numbers and insights. Be specific and direct.'
        )
