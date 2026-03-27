"""Eval CLI command — run structured evaluation against a database."""

import json
import sys

from ..core.config import AskMeDBConfig
from .connect import add_db_arguments, connect_db


def register(subparsers):
    """Register the eval subcommand."""
    p = subparsers.add_parser(
        "eval",
        help="Run evaluation questions and compute accuracy metrics",
    )
    add_db_arguments(p)
    p.add_argument(
        "--questions", required=True, help="Path to questions.json file"
    )
    p.add_argument("--schema", help="Path to schema.json file (optional, auto-detected if omitted)")
    p.add_argument("--business-rules", help="Path to business_rules.json file")
    p.add_argument("--query-patterns", help="Path to query_patterns.sql file")
    p.add_argument("--output", "-o", help="Output path for JSON report")
    p.add_argument("--model", default=AskMeDBConfig.model, help="LLM model to use")
    p.add_argument(
        "--min-success-rate",
        type=float,
        default=0.0,
        help="Minimum success rate (0.0-1.0). Exit with code 1 if below threshold.",
    )
    p.set_defaults(func=run_eval)


def _print_summary(summary: dict, results: list[dict]):
    """Print a formatted summary table to the terminal."""
    print("\n" + "=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)
    print(f"  Total questions:      {summary['total_questions']}")
    print(f"  Success rate:         {summary['success_rate']:.1%}")
    print(f"  Exact match rate:     {summary['exact_match_rate']:.1%}")
    print(f"  Semantic match rate:  {summary['semantic_match_rate']:.1%}")
    print(f"  Correction rate:      {summary['correction_rate']:.1%}")
    print(f"  Avg latency:          {summary['avg_latency_ms']:.0f}ms")
    print("=" * 60)

    # Per-question results
    print(f"\n{'#':>3} {'Status':>7} {'Exact':>6} {'Sem.':>6} {'Corr':>5} {'ms':>7}  Question")
    print("-" * 70)
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        exact = "Y" if r["exact_match"] else "N"
        semantic = "Y" if r["semantic_match"] else "N"
        corr = str(r["correction_attempts"])
        ms = f"{r['latency_ms']:.0f}"
        q = r["question"][:40]
        print(f"{r['index']:>3} {status:>7} {exact:>6} {semantic:>6} {corr:>5} {ms:>7}  {q}")

    print()


def run_eval(args):
    """Execute the eval command."""
    # Load questions
    with open(args.questions) as f:
        questions = json.load(f)

    print(f"Loaded {len(questions)} questions from {args.questions}")

    # Connect to DB
    db, csv_schema = connect_db(args)

    # Set up schema: explicit --schema flag > CSV auto-schema > AutoSchemaProvider
    if args.schema:
        from ..context.schema import JSONSchemaProvider
        schema = JSONSchemaProvider(args.schema)
    elif csv_schema:
        schema = csv_schema
    else:
        from ..context.schema import AutoSchemaProvider
        schema = AutoSchemaProvider(db)

    # Create engine
    config = AskMeDBConfig(model=args.model, read_only=True)
    from ..core.engine import AskMeDBEngine
    engine = AskMeDBEngine(
        db=db,
        schema=schema,
        config=config,
        business_rules=args.business_rules,
        query_patterns=args.query_patterns,
    )

    # Run evaluation
    from ..eval.runner import EvalRunner
    from ..eval.metrics import compute_metrics

    runner = EvalRunner(engine=engine, db=db)
    print(f"Running evaluation with {args.model}...\n")
    results = runner.run(questions)
    summary = compute_metrics(results)

    # Output
    _print_summary(summary, results)

    report = {"summary": summary, "results": results}

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Full report written to {args.output}")

    # Exit code based on threshold
    if summary["success_rate"] < args.min_success_rate:
        print(
            f"FAIL: Success rate {summary['success_rate']:.1%} is below "
            f"threshold {args.min_success_rate:.1%}",
            file=sys.stderr,
        )
        sys.exit(1)

    db.close()
