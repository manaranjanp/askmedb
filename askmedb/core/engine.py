"""AskMeDBEngine — the main orchestrator for the AskMeDB library."""

from typing import Callable, Optional

from .config import AskMeDBConfig
from .result import QueryResult
from ..db.base import BaseDBConnector
from ..llm.base import BaseLLMProvider
from ..llm.litellm_provider import LiteLLMProvider
from ..context.schema import SchemaProvider, JSONSchemaProvider, DictSchemaProvider
from ..context.builder import ContextBuilder
from ..context.prompts import PromptTemplate
from ..pipeline.parser import parse_sql_response, parse_answer_response
from ..pipeline.conversation import ConversationManager
from ..pipeline.correction import SelfCorrector
from ..pipeline.validation import validate_results, format_results_for_llm


class AskMeDBEngine:
    """Main orchestrator — the single class most developers will use.

    Handles the full pipeline: question -> SQL generation -> execution ->
    self-correction -> answer synthesis.

    Args:
        db: Database connector instance.
        schema: Schema metadata as a SchemaProvider, dict, or path to a JSON file.
        config: Engine configuration.
        llm: LLM provider instance. Defaults to LiteLLMProvider with config.model.
        business_rules: Optional business rules as dict, JSON string, or file path.
        query_patterns: Optional SQL example patterns as string or file path.
        prompt_template: Optional custom prompt template.
        agent_description: Description of the agent role for the system prompt.

    Example:
        >>> from askmedb import AskMeDBEngine, SQLiteConnector
        >>> engine = AskMeDBEngine(
        ...     db=SQLiteConnector("my.db"),
        ...     schema={"tables": [...]},
        ... )
        >>> result = engine.ask("How many users do we have?")
        >>> print(result.answer)
    """

    def __init__(
        self,
        db: BaseDBConnector,
        schema: SchemaProvider | dict | str,
        config: AskMeDBConfig = None,
        llm: BaseLLMProvider = None,
        business_rules: Optional[dict | str] = None,
        query_patterns: Optional[str] = None,
        prompt_template: Optional[PromptTemplate] = None,
        agent_description: str = "You are a data analyst agent. You answer natural language questions by generating SQL queries.",
    ):
        self.config = config or AskMeDBConfig()
        self.db = db
        self.llm = llm or LiteLLMProvider(
            model=self.config.model,
            max_retries=self.config.max_retries,
        )

        # Resolve schema provider
        if isinstance(schema, SchemaProvider):
            schema_provider = schema
        elif isinstance(schema, dict):
            schema_provider = DictSchemaProvider(schema)
        elif isinstance(schema, str):
            schema_provider = JSONSchemaProvider(schema)
        else:
            raise TypeError(f"schema must be a SchemaProvider, dict, or str path, got {type(schema)}")

        # Build context
        self._context_builder = ContextBuilder(
            schema_provider=schema_provider,
            prompt_template=prompt_template,
            business_rules=business_rules,
            query_patterns=query_patterns,
            dialect=db.get_dialect(),
            agent_description=agent_description,
        )

        # Pipeline components
        self._conversation = ConversationManager(max_turns=self.config.max_conversation_turns)
        self._corrector = SelfCorrector(
            llm=self.llm,
            prompt_template=self._context_builder.prompt_template,
            learnings_path=self.config.learnings_path if self.config.enable_learnings else None,
            sql_temperature=self.config.sql_temperature,
            sql_max_tokens=self.config.sql_max_tokens,
        )

        # Event hooks — set these to receive pipeline events
        self.on_reasoning: Optional[Callable[[str], None]] = None
        self.on_sql_generated: Optional[Callable[[str], None]] = None
        self.on_sql_error: Optional[Callable[[str, str, int], None]] = None
        self.on_sql_corrected: Optional[Callable[[str, str], None]] = None
        self.on_results: Optional[Callable[[list, list], None]] = None
        self.on_warning: Optional[Callable[[str], None]] = None
        self.on_answer: Optional[Callable[[str], None]] = None
        self.on_learning_saved: Optional[Callable[[], None]] = None

    def ask(self, question: str, conversation_id: str = "default") -> QueryResult:
        """Ask a natural-language question and get a result.

        Args:
            question: The question to ask in natural language.
            conversation_id: Conversation session ID for multi-turn support.

        Returns:
            QueryResult with SQL, data, answer, and metadata.
        """
        result = QueryResult(question=question)

        # Build system prompt with all context layers
        learnings = self._corrector.learnings if self.config.enable_learnings else []

        if self.config.system_prompt_override:
            system_prompt = self.config.system_prompt_override
        else:
            system_prompt = self._context_builder.build_system_prompt(
                question=question,
                learnings=learnings,
            )
            if self.config.system_prompt_prefix:
                system_prompt = self.config.system_prompt_prefix + "\n\n" + system_prompt

        # Assemble messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._conversation.get_history(conversation_id))
        messages.append({"role": "user", "content": question})

        # Step 1: Generate SQL
        response = self.llm.generate(
            messages,
            temperature=self.config.sql_temperature,
            max_tokens=self.config.sql_max_tokens,
        )
        sql, reasoning = parse_sql_response(response)
        result.reasoning = reasoning

        if not sql:
            # No SQL generated — conversational response
            answer = parse_answer_response(response)
            result.answer = answer
            self._conversation.add_turn("user", question, conversation_id)
            self._conversation.add_turn("assistant", answer, conversation_id)
            if self.on_answer:
                self.on_answer(answer)
            return result

        result.sql = sql
        if self.on_reasoning and reasoning:
            self.on_reasoning(reasoning)
        if self.on_sql_generated:
            self.on_sql_generated(sql)

        # Step 2: Execute SQL with self-correction loop
        original_sql = sql
        last_error = None
        columns, rows = [], []

        for attempt in range(self.config.max_correction_attempts):
            try:
                columns, rows = self.db.execute(sql)
                warnings = validate_results(columns, rows)
                for w in warnings:
                    if self.on_warning:
                        self.on_warning(w)
                result.warnings = warnings
                break
            except Exception as e:
                last_error = str(e)
                result.correction_attempts = attempt + 1
                if self.on_sql_error:
                    self.on_sql_error(last_error, sql, attempt + 1)

                if attempt < self.config.max_correction_attempts - 1:
                    sql, correction_reasoning = self._corrector.attempt_correction(
                        error=last_error,
                        original_sql=sql,
                        messages=messages,
                    )
                    if not sql:
                        result.error = f"Could not generate a corrected query. Last error: {last_error}"
                        self._conversation.add_turn("user", question, conversation_id)
                        self._conversation.add_turn(
                            "assistant",
                            f"I wasn't able to answer this question. Error: {last_error}",
                            conversation_id,
                        )
                        return result

                    result.sql = sql
                    if self.on_sql_corrected and correction_reasoning:
                        self.on_sql_corrected(sql, correction_reasoning)
                else:
                    result.error = f"Max correction attempts reached. Last error: {last_error}"
                    self._conversation.add_turn("user", question, conversation_id)
                    self._conversation.add_turn(
                        "assistant",
                        f"I wasn't able to answer this question. The query kept failing with: {last_error}",
                        conversation_id,
                    )
                    return result

        # Save learning if self-correction was needed
        if sql != original_sql and last_error and self.config.enable_learnings:
            lesson = f"Original query used invalid syntax. Error: {last_error}. Fixed by rewriting the query."
            self._corrector.save_learning(question, last_error, original_sql, sql, lesson)
            if self.on_learning_saved:
                self.on_learning_saved()

        result.columns = columns
        result.rows = rows

        if self.on_results:
            self.on_results(columns, rows)

        # Step 3: Generate human-readable answer
        results_text = format_results_for_llm(columns, rows, max_rows=self.config.max_result_rows)
        answer_prompt = self._context_builder.prompt_template.build_answer_prompt(question)

        answer_messages = messages + [
            {
                "role": "assistant",
                "content": f"I ran this SQL query:\n```sql\n{sql}\n```\n\nResults:\n{results_text}",
            },
            {
                "role": "user",
                "content": answer_prompt,
            },
        ]

        answer = self.llm.generate(
            answer_messages,
            temperature=self.config.answer_temperature,
            max_tokens=self.config.answer_max_tokens,
        )
        answer = parse_answer_response(answer)
        result.answer = answer

        if self.on_answer:
            self.on_answer(answer)

        # Update conversation history
        self._conversation.add_turn("user", question, conversation_id)
        self._conversation.add_turn("assistant", f"SQL: {sql}\nAnswer: {answer}", conversation_id)

        return result

    def reset_conversation(self, conversation_id: str = "default"):
        """Clear conversation history for a session."""
        self._conversation.reset(conversation_id)

    def reset_all_conversations(self):
        """Clear all conversation histories."""
        self._conversation.reset_all()

    def close(self):
        """Close the database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
