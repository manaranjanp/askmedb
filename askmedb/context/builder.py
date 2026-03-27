"""Context builder — assembles schema, rules, patterns, and learnings into prompts."""

import json
import re
from typing import Optional

from .schema import SchemaProvider
from .prompts import PromptTemplate


class ContextBuilder:
    """Assembles context layers into system prompts.

    Args:
        schema_provider: Schema metadata provider.
        prompt_template: Prompt template to use. Created automatically if not provided.
        business_rules: Business rules as a dict, JSON string, or file path.
        query_patterns: SQL example patterns as a string or file path.
        dialect: SQL dialect (used if prompt_template is not provided).
        agent_description: Agent description (used if prompt_template is not provided).
    """

    def __init__(
        self,
        schema_provider: SchemaProvider,
        prompt_template: Optional[PromptTemplate] = None,
        business_rules: Optional[dict | str] = None,
        query_patterns: Optional[str] = None,
        dialect: str = "sqlite",
        agent_description: str = "You are a data analyst agent. You answer natural language questions by generating SQL queries.",
        read_only: bool = False,
    ):
        self.schema_provider = schema_provider
        self.prompt_template = prompt_template or PromptTemplate(
            agent_description=agent_description,
            dialect=dialect,
            read_only=read_only,
        )
        self._business_rules = self._load_business_rules(business_rules)
        self._query_patterns = self._load_query_patterns(query_patterns)

    def _load_business_rules(self, rules: Optional[dict | str]) -> Optional[dict]:
        """Load business rules from dict, JSON string, or file path."""
        if rules is None:
            return None
        if isinstance(rules, dict):
            return rules
        # Try as file path first
        try:
            with open(rules) as f:
                return json.load(f)
        except (FileNotFoundError, IsADirectoryError):
            pass
        # Try as JSON string
        try:
            return json.loads(rules)
        except (json.JSONDecodeError, TypeError):
            return None

    def _load_query_patterns(self, patterns: Optional[str]) -> Optional[str]:
        """Load query patterns from string or file path."""
        if patterns is None:
            return None
        # Try as file path
        try:
            with open(patterns) as f:
                return f.read()
        except (FileNotFoundError, IsADirectoryError):
            pass
        # Use as raw string
        return patterns

    def format_business_rules(self) -> str:
        """Format business rules into a readable string."""
        if not self._business_rules:
            return ""

        lines = []

        if "metrics" in self._business_rules:
            lines.append("METRIC DEFINITIONS:")
            for metric in self._business_rules["metrics"]:
                lines.append(f"\n{metric['name']}:")
                lines.append(f"  Definition: {metric['definition']}")
                lines.append(f"  SQL hint: {metric['sql_hint']}")
                for gotcha in metric.get("gotchas", []):
                    lines.append(f"  WARNING: {gotcha}")

        if "common_gotchas" in self._business_rules:
            lines.append("\n\nCOMMON GOTCHAS:")
            for gotcha in self._business_rules["common_gotchas"]:
                lines.append(f"\n{gotcha['issue']}:")
                lines.append(f"  {gotcha['note']}")

        return "\n".join(lines)

    def retrieve_query_patterns(self, question: str) -> str:
        """Retrieve relevant query patterns based on keyword matching."""
        if not self._query_patterns:
            return ""

        # Split into individual patterns
        patterns = self._query_patterns.split("\n\n-- Pattern:")
        patterns = [
            ("-- Pattern:" + p if not p.startswith("-- Pattern:") else p)
            for p in patterns
        ]
        patterns = [p.strip() for p in patterns if p.strip()]

        # Tokenize the question
        question_words = set(re.findall(r'\w+', question.lower()))

        # Score each pattern by keyword overlap
        scored = []
        for pattern in patterns:
            kw_match = re.search(r"Keywords:\s*(.+)", pattern, re.IGNORECASE)
            if kw_match:
                pattern_keywords = set(kw_match.group(1).lower().replace(",", " ").split())
                overlap = len(question_words & pattern_keywords)
                if overlap > 0:
                    scored.append((overlap, pattern))

        scored.sort(key=lambda x: x[0], reverse=True)
        relevant = [p for _, p in scored[:3]]

        if relevant:
            return "RELEVANT SQL EXAMPLES:\n\n" + "\n\n".join(relevant)
        return ""

    def format_learnings(self, learnings: list[dict]) -> str:
        """Format learnings from past self-corrections."""
        if not learnings:
            return ""

        recent = learnings[-5:]
        lines = ["PAST LEARNINGS (avoid these mistakes):"]
        for entry in recent:
            lines.append(f"\n- Question: {entry.get('question', 'N/A')}")
            lines.append(f"  Error: {entry.get('error', 'N/A')}")
            lines.append(f"  Lesson: {entry.get('lesson', 'N/A')}")

        return "\n".join(lines)

    def build_system_prompt(
        self,
        question: str = "",
        learnings: Optional[list[dict]] = None,
    ) -> str:
        """Build the complete system prompt with all context layers.

        Args:
            question: User question (used for pattern matching).
            learnings: Optional list of learning dicts from self-correction.

        Returns:
            Complete system prompt string.
        """
        schema_text = self.schema_provider.format_schema()
        rules_text = self.format_business_rules()
        patterns_text = self.retrieve_query_patterns(question)
        learnings_text = self.format_learnings(learnings or [])

        return self.prompt_template.build(
            schema_text=schema_text,
            business_rules_text=rules_text,
            query_patterns_text=patterns_text,
            learnings_text=learnings_text,
        )
