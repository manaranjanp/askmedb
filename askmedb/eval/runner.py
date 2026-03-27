"""Eval runner — orchestrates running questions through an AskMeDB engine and collecting results."""

import time

from ..core.engine import AskMeDBEngine
from ..db.base import BaseDBConnector
from .metrics import sql_exact_match, sql_semantic_match, answer_contains_check


class EvalRunner:
    """Runs a set of evaluation questions through an AskMeDB engine.

    Args:
        engine: An initialized AskMeDBEngine instance.
        db: The database connector (used for semantic match comparisons).
    """

    def __init__(self, engine: AskMeDBEngine, db: BaseDBConnector):
        self.engine = engine
        self.db = db

    def run(self, questions: list[dict]) -> list[dict]:
        """Run all questions and return per-question results.

        Args:
            questions: List of dicts with 'question', 'expected_sql',
                       and optionally 'expected_answer_contains'.

        Returns:
            List of result dicts with evaluation details.
        """
        results = []
        for i, q in enumerate(questions):
            question_text = q["question"]
            expected_sql = q.get("expected_sql", "")
            expected_fragments = q.get("expected_answer_contains", [])

            # Reset conversation for each eval question
            self.engine.reset_conversation("eval")

            start = time.monotonic()
            query_result = self.engine.ask(question_text, conversation_id="eval")
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            result = {
                "index": i + 1,
                "question": question_text,
                "expected_sql": expected_sql,
                "generated_sql": query_result.sql,
                "answer": query_result.answer,
                "success": query_result.success,
                "error": query_result.error,
                "correction_attempts": query_result.correction_attempts,
                "latency_ms": elapsed_ms,
                "exact_match": False,
                "semantic_match": False,
                "answer_match": None,
            }

            if query_result.success and expected_sql:
                result["exact_match"] = sql_exact_match(query_result.sql, expected_sql)
                result["semantic_match"] = sql_semantic_match(
                    self.db, query_result.sql, expected_sql
                )

            if query_result.success and expected_fragments:
                result["answer_match"] = answer_contains_check(
                    query_result.answer, expected_fragments
                )

            results.append(result)

        return results
