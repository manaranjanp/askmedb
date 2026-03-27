"""FederatedEngine — route natural-language questions across multiple databases."""

import json
from typing import Optional, Callable

from .config import AskMeDBConfig
from .result import QueryResult
from .engine import AskMeDBEngine
from ..llm.base import BaseLLMProvider
from ..llm.litellm_provider import LiteLLMProvider
from ..pipeline.parser import parse_answer_response


_ROUTING_PROMPT = """You are a database routing agent. You have access to the following databases:

{databases}

Given a user question, determine which database(s) should be queried to answer it.

Return your answer as a JSON object with this exact format:
{{"databases": ["db_name1"], "reasoning": "brief explanation"}}

If the question requires data from multiple databases, list all relevant ones.
If you're unsure, list the most likely database.

Return ONLY the JSON object — no markdown fences, no extra text."""


class FederatedEngine:
    """Routes natural-language questions across multiple AskMeDB engines.

    Each engine is registered under a namespace (e.g., "sales", "support").
    A routing LLM call determines which engine(s) should handle each question.

    Args:
        engines: Dict mapping namespace names to AskMeDBEngine instances.
        config: Configuration (used for the routing LLM call). Optional.
        llm: LLM provider for routing. Defaults to LiteLLMProvider with config.model.

    Example:
        >>> federated = FederatedEngine({
        ...     "sales": sales_engine,
        ...     "support": support_engine,
        ... })
        >>> result = federated.ask("Which customers have open support tickets?")
    """

    def __init__(
        self,
        engines: dict[str, AskMeDBEngine],
        config: AskMeDBConfig | None = None,
        llm: BaseLLMProvider | None = None,
    ):
        if not engines:
            raise ValueError("At least one engine must be provided.")
        self.engines = engines
        self.config = config or AskMeDBConfig()
        self.llm = llm or LiteLLMProvider(
            model=self.config.model,
            max_retries=self.config.max_retries,
        )

        # Event hooks
        self.on_routing: Optional[Callable[[list[str], str], None]] = None

    def _build_database_descriptions(self) -> str:
        """Build descriptions of all registered databases for the routing prompt."""
        lines = []
        for name, engine in self.engines.items():
            schema = engine._context_builder.schema_provider.get_schema()
            db_desc = schema.get("description", "No description available")
            tables = [t["name"] for t in schema.get("tables", [])]
            lines.append(
                f"- **{name}**: {db_desc}\n"
                f"  Tables: {', '.join(tables)}"
            )
        return "\n".join(lines)

    def _route_question(self, question: str) -> tuple[list[str], str]:
        """Use LLM to determine which database(s) should handle the question.

        Returns:
            Tuple of (list of database names, reasoning string).
        """
        db_descriptions = self._build_database_descriptions()
        prompt = _ROUTING_PROMPT.format(databases=db_descriptions)

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=256,
        )

        # Parse the routing response
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            routing = json.loads(text)
            db_names = routing.get("databases", [])
            reasoning = routing.get("reasoning", "")
        except (json.JSONDecodeError, KeyError):
            # Fallback: try to find database names in the response
            db_names = [
                name for name in self.engines
                if name.lower() in response.lower()
            ]
            reasoning = response
            if not db_names:
                # Default to first engine
                db_names = [next(iter(self.engines))]

        # Validate names
        valid_names = [n for n in db_names if n in self.engines]
        if not valid_names:
            valid_names = [next(iter(self.engines))]

        return valid_names, reasoning

    def ask(
        self,
        question: str,
        conversation_id: str = "default",
    ) -> QueryResult:
        """Ask a question, routing it to the appropriate database(s).

        For single-database questions, delegates directly to that engine.
        For multi-database questions, queries each and synthesizes a combined answer.

        Args:
            question: Natural-language question.
            conversation_id: Conversation session ID.

        Returns:
            QueryResult with answer, SQL, and data.
        """
        # Route the question
        target_dbs, routing_reasoning = self._route_question(question)

        if self.on_routing:
            self.on_routing(target_dbs, routing_reasoning)

        if len(target_dbs) == 1:
            # Single database — delegate directly
            return self.engines[target_dbs[0]].ask(question, conversation_id)

        # Multi-database — query each and combine
        sub_results = {}
        for db_name in target_dbs:
            sub_results[db_name] = self.engines[db_name].ask(question, conversation_id)

        # Synthesize a combined answer
        combined = self._synthesize_multi_result(question, sub_results)
        return combined

    def _synthesize_multi_result(
        self,
        question: str,
        sub_results: dict[str, QueryResult],
    ) -> QueryResult:
        """Combine results from multiple databases into a single answer."""
        result = QueryResult(question=question)

        # Collect all SQL and data
        sql_parts = []
        all_answers = []
        total_corrections = 0
        has_error = False

        for db_name, sub in sub_results.items():
            if sub.error:
                has_error = True
                all_answers.append(f"[{db_name}] Error: {sub.error}")
            else:
                sql_parts.append(f"-- [{db_name}]\n{sub.sql}")
                all_answers.append(f"[{db_name}] {sub.answer}")
                total_corrections += sub.correction_attempts

        result.sql = "\n\n".join(sql_parts)
        result.correction_attempts = total_corrections

        if has_error and not any(sub.success for sub in sub_results.values()):
            result.error = "All database queries failed."
            result.answer = "\n".join(all_answers)
            return result

        # Use LLM to synthesize a combined answer
        context = "\n\n".join(all_answers)
        synthesis_prompt = (
            f"The following answers were obtained from multiple databases for the question: "
            f'"{question}"\n\n{context}\n\n'
            f"Please synthesize these into a single, coherent answer."
        )

        combined_answer = self.llm.generate(
            messages=[
                {"role": "system", "content": "You synthesize answers from multiple data sources into clear, concise responses."},
                {"role": "user", "content": synthesis_prompt},
            ],
            temperature=0.3,
            max_tokens=self.config.answer_max_tokens,
        )
        result.answer = parse_answer_response(combined_answer)

        # Use columns/rows from the first successful result
        for sub in sub_results.values():
            if sub.success:
                result.columns = sub.columns
                result.rows = sub.rows
                break

        return result

    def reset_conversation(self, conversation_id: str = "default"):
        """Reset conversation history across all engines."""
        for engine in self.engines.values():
            engine.reset_conversation(conversation_id)

    def reset_all_conversations(self):
        """Reset all conversations across all engines."""
        for engine in self.engines.values():
            engine.reset_all_conversations()

    def close(self):
        """Close all database connections."""
        for engine in self.engines.values():
            engine.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
