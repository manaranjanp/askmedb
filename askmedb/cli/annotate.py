"""Schema annotation command — uses an LLM to auto-generate schema descriptions."""

import json
import sys

from ..core.config import AskMeDBConfig
from ..llm.litellm_provider import LiteLLMProvider
from .connect import add_db_arguments, connect_db


def register(subparsers):
    """Register the annotate subcommand."""
    p = subparsers.add_parser(
        "annotate",
        help="Auto-generate schema.json with LLM-powered table and column descriptions",
    )
    add_db_arguments(p)
    p.add_argument("--output", "-o", default="schema.json", help="Output file path (default: schema.json)")
    p.add_argument("--model", default=AskMeDBConfig.model, help="LLM model to use")
    p.add_argument("--samples", type=int, default=5, help="Sample rows per table (default: 5)")
    p.set_defaults(func=run_annotate)


def _sample_rows(db, table_name: str, n: int) -> list[dict]:
    """Fetch N sample rows from a table."""
    try:
        columns, rows = db.execute(f"SELECT * FROM {table_name} LIMIT {n}")
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []


def _build_annotation_prompt(schema: dict, samples: dict[str, list[dict]]) -> str:
    """Build the LLM prompt for schema annotation."""
    lines = [
        "You are a database documentation expert. Given the following database schema "
        "and sample data, generate clear, concise descriptions for each table and column.",
        "",
        "Return your response as a valid JSON object with the exact same structure as the "
        "input schema, but with meaningful 'description' fields filled in for the database, "
        "every table, and every column.",
        "",
        "Guidelines:",
        "- Table descriptions should explain what the table stores and its role in the database",
        "- Column descriptions should explain what the column contains, its format, and any constraints",
        "- For foreign keys, mention the relationship (e.g., 'References customers.customer_id')",
        "- For enum-like columns, list the possible values if visible in the sample data",
        "- Keep descriptions concise (1-2 sentences each)",
        "",
        "== SCHEMA ==",
        json.dumps(schema, indent=2),
        "",
    ]

    if samples:
        lines.append("== SAMPLE DATA ==")
        for table_name, rows in samples.items():
            if rows:
                lines.append(f"\nTable: {table_name}")
                lines.append(json.dumps(rows, indent=2, default=str))

    lines.extend([
        "",
        "Return ONLY the JSON object — no markdown fences, no explanation, just valid JSON.",
    ])

    return "\n".join(lines)


def _parse_llm_response(response: str) -> dict:
    """Parse the LLM response as JSON, stripping markdown fences if present."""
    text = response.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


def run_annotate(args):
    """Execute the annotate command."""
    print(f"Connecting to {args.type} database...")
    db, csv_schema = connect_db(args)

    # Get raw schema — use CSV schema provider if available, else AutoSchemaProvider
    if csv_schema:
        schema = csv_schema.get_schema()
    else:
        from ..context.schema import AutoSchemaProvider
        provider = AutoSchemaProvider(db)
        schema = provider.get_schema()

    print(f"Found {len(schema.get('tables', []))} tables")

    # Sample rows from each table
    samples = {}
    for table in schema.get("tables", []):
        table_name = table["name"]
        rows = _sample_rows(db, table_name, args.samples)
        if rows:
            samples[table_name] = rows
            print(f"  Sampled {len(rows)} rows from {table_name}")

    # Build prompt and call LLM
    prompt = _build_annotation_prompt(schema, samples)
    llm = LiteLLMProvider(model=args.model)

    print(f"Generating descriptions with {args.model}...")
    response = llm.generate(
        messages=[
            {"role": "system", "content": "You are a database documentation expert. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=4096,
    )

    try:
        annotated_schema = _parse_llm_response(response)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse LLM response as JSON: {e}", file=sys.stderr)
        print("Raw response saved to annotate_error.txt", file=sys.stderr)
        with open("annotate_error.txt", "w") as f:
            f.write(response)
        sys.exit(1)

    # Write output
    with open(args.output, "w") as f:
        json.dump(annotated_schema, f, indent=2)

    print(f"Schema written to {args.output}")
    db.close()
