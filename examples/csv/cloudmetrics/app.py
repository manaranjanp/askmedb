"""
CloudMetrics Data Agent — CSV/pandas CLI application using AskMeDB.

Loads five interrelated CSV files into a shared in-memory SQLite database,
enabling natural language queries with full JOIN support across all tables.

Usage:
    1. Generate data: python examples/setup_db.py
    2. Install pandas extra: pip install askmedb[pandas]
    3. Set your API key: export ANTHROPIC_API_KEY=...
    4. Run: python examples/csv/cloudmetrics/app.py
"""

import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Add project root to path so askmedb can be imported without installing
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, PROJECT_ROOT)

from askmedb import AskMeDBEngine, AskMeDBConfig, PandasConnector, PandasSchemaProvider

# Load .env file
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

console = Console()

# Paths
EXAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(EXAMPLE_DIR, "..", "..", "data")

# Inter-table relationships — tells the LLM how to JOIN the CSV-backed tables
RELATIONSHIPS = [
    {"from_table": "subscriptions",   "from_col": "customer_id",    "to_table": "customers",     "to_col": "customer_id"},
    {"from_table": "subscriptions",   "from_col": "plan_id",         "to_table": "plans",         "to_col": "plan_id"},
    {"from_table": "invoices",        "from_col": "subscription_id", "to_table": "subscriptions", "to_col": "subscription_id"},
    {"from_table": "invoices",        "from_col": "customer_id",     "to_table": "customers",     "to_col": "customer_id"},
    {"from_table": "support_tickets", "from_col": "customer_id",     "to_table": "customers",     "to_col": "customer_id"},
]


def create_engine() -> AskMeDBEngine:
    """Load CSV files and configure the AskMeDB engine."""
    model = os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001")

    db = PandasConnector({
        "customers":       os.path.join(DATA_DIR, "customers.csv"),
        "plans":           os.path.join(DATA_DIR, "plans.csv"),
        "subscriptions":   os.path.join(DATA_DIR, "subscriptions.csv"),
        "invoices":        os.path.join(DATA_DIR, "invoices.csv"),
        "support_tickets": os.path.join(DATA_DIR, "support_tickets.csv"),
    })

    schema = PandasSchemaProvider(
        db,
        relationships=RELATIONSHIPS,
        database_name="cloudmetrics",
        description=(
            "CloudMetrics SaaS subscription analytics. "
            "Contains customer, subscription, billing, and support data "
            "for a B2B project management SaaS product. Loaded from CSV files."
        ),
    )

    config = AskMeDBConfig(model=model)

    engine = AskMeDBEngine(
        db=db,
        schema=schema,
        config=config,
        agent_description=(
            "You are a data analyst agent for CloudMetrics, a B2B SaaS company "
            "that sells project management software. "
            "You answer natural language questions by generating SQL queries. "
            "Data is loaded from CSV files into an in-memory SQLite database."
        ),
    )

    # Wire up Rich CLI display via event hooks
    engine.on_reasoning = lambda r: console.print(
        Panel(r, title="Reasoning", border_style="blue")
    )
    engine.on_sql_generated = lambda sql: console.print(
        Panel(
            Syntax(sql, "sql", theme="monokai", line_numbers=False),
            title="Generated SQL",
            border_style="green",
        )
    )
    engine.on_sql_error = lambda err, sql, attempt: console.print(
        f"[red]SQL Error (attempt {attempt}): {err}[/red]"
    )
    engine.on_sql_corrected = lambda sql, reason: (
        console.print(Panel(reason, title="Correction", border_style="yellow")),
        console.print(
            Panel(
                Syntax(sql, "sql", theme="monokai", line_numbers=False),
                title="Corrected SQL",
                border_style="yellow",
            )
        ),
    )
    engine.on_warning = lambda w: console.print(f"[yellow]Warning: {w}[/yellow]")
    engine.on_results = lambda cols, rows: _display_results(cols, rows)

    return engine


def _display_results(columns: list[str], rows: list[tuple], max_rows: int = 50):
    """Display query results as a Rich table."""
    if not rows:
        return

    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    for col in columns:
        table.add_column(col)

    for row in rows[:max_rows]:
        table.add_row(*[str(v) if v is not None else "NULL" for v in row])

    if len(rows) > max_rows:
        table.add_row(
            *[f"... ({len(rows) - max_rows} more rows)" if i == 0 else "" for i in range(len(columns))]
        )

    console.print(Panel(table, title=f"Results ({len(rows)} rows)", border_style="cyan"))


def print_help():
    """Print help information."""
    console.print(
        Panel(
            "[bold]CloudMetrics Data Agent (CSV)[/bold]\n\n"
            "Ask questions about your SaaS business data in plain English.\n"
            "Data is loaded from CSV files — no database server required!\n\n"
            "[bold]Commands:[/bold]\n"
            "  [cyan]help[/cyan]     - Show this help message\n"
            "  [cyan]samples[/cyan]  - Show sample queries you can try\n"
            "  [cyan]reset[/cyan]    - Clear conversation history\n"
            "  [cyan]exit[/cyan]     - Quit the agent\n\n"
            "[bold]Examples:[/bold]\n"
            '  "How many customers do we have?"\n'
            '  "What is our total MRR right now?"\n'
            '  "Break that down by plan" (follow-up)\n'
            '  "Average ticket resolution time by priority?"',
            title="Help",
            border_style="blue",
        )
    )


def print_samples():
    """Print sample queries."""
    from sample_queries import SAMPLE_QUERIES

    console.print(
        Panel(
            "\n".join(f"  [cyan]{i}.[/cyan] {q}" for i, q in enumerate(SAMPLE_QUERIES, 1)),
            title="Sample Queries",
            border_style="green",
        )
    )


def main():
    console.print(
        Panel.fit(
            "[bold blue]CloudMetrics Data Agent (CSV)[/bold blue]\n"
            "[dim]Powered by AskMeDB | Ask questions about your SaaS data[/dim]\n"
            "[dim]Type 'help' for commands, 'exit' to quit[/dim]",
            border_style="blue",
        )
    )

    try:
        console.print("[dim]Loading CSV files...[/dim]")
        engine = create_engine()
        console.print("[dim]Ready.[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to initialize: {e}[/red]")
        sys.exit(1)

    while True:
        try:
            question = console.input("\n[bold green]You>[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not question:
            continue

        cmd = question.lower()
        if cmd in ("exit", "quit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break
        elif cmd == "help":
            print_help()
            continue
        elif cmd == "samples":
            print_samples()
            continue
        elif cmd == "reset":
            engine.reset_conversation()
            console.print("[dim]Conversation history cleared.[/dim]")
            continue

        try:
            console.print("\n[dim]Thinking...[/dim]")
            result = engine.ask(question)
            console.print(
                Panel(
                    Markdown(result.answer),
                    title="Answer",
                    border_style="green",
                )
            )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
