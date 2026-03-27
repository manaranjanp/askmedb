"""Evaluation metrics for comparing generated SQL against expected SQL."""

import re


def normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison: lowercase, collapse whitespace, strip trailing semicolons."""
    sql = sql.strip().rstrip(";").strip()
    sql = re.sub(r"\s+", " ", sql.lower())
    return sql


def sql_exact_match(generated: str, expected: str) -> bool:
    """Check if two SQL statements are equivalent after normalization."""
    return normalize_sql(generated) == normalize_sql(expected)


def sql_semantic_match(db, generated: str, expected: str) -> bool:
    """Check if two SQL statements produce the same result set.

    Executes both queries and compares their output (columns + sorted rows).
    Returns False if either query fails.
    """
    try:
        gen_cols, gen_rows = db.execute(generated)
        exp_cols, exp_rows = db.execute(expected)
    except Exception:
        return False

    if gen_cols != exp_cols:
        return False

    return sorted(gen_rows) == sorted(exp_rows)


def answer_contains_check(answer: str, expected_fragments: list[str]) -> bool:
    """Check if the answer contains all expected fragments."""
    answer_lower = answer.lower()
    return all(frag.lower() in answer_lower for frag in expected_fragments)


def compute_metrics(results: list[dict]) -> dict:
    """Compute aggregate metrics from a list of eval result dicts.

    Each result dict should have: success, exact_match, semantic_match,
    correction_attempts, latency_ms.
    """
    total = len(results)
    if total == 0:
        return {
            "total_questions": 0,
            "success_rate": 0.0,
            "exact_match_rate": 0.0,
            "semantic_match_rate": 0.0,
            "correction_rate": 0.0,
            "avg_latency_ms": 0.0,
        }

    successes = sum(1 for r in results if r.get("success"))
    exact_matches = sum(1 for r in results if r.get("exact_match"))
    semantic_matches = sum(1 for r in results if r.get("semantic_match"))
    corrections = sum(1 for r in results if r.get("correction_attempts", 0) > 0)
    total_latency = sum(r.get("latency_ms", 0) for r in results)

    return {
        "total_questions": total,
        "success_rate": round(successes / total, 4),
        "exact_match_rate": round(exact_matches / total, 4),
        "semantic_match_rate": round(semantic_matches / total, 4),
        "correction_rate": round(corrections / total, 4),
        "avg_latency_ms": round(total_latency / total, 1),
    }
