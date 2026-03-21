"""
AskMeDB Quickstart — Minimal CSV/pandas example with table relationships.

Loads the five CloudMetrics CSV files into a shared in-memory SQLite database
so that SQL JOINs work seamlessly across all tables.

Usage:
    1. Generate data: python examples/setup_db.py
    2. Install pandas extra: pip install askmedb[pandas]
    3. Set your API key: export ANTHROPIC_API_KEY=...
    4. Run: python examples/csv/quickstart.py
"""

import os
import sys

from dotenv import load_dotenv

# Add project root to path so askmedb can be imported without installing
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from askmedb import AskMeDBEngine, AskMeDBConfig, PandasConnector, PandasSchemaProvider

# Path to the CSV files bundled with this example
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Load all five CSV files into a shared in-memory SQLite database
db = PandasConnector({
    "customers":       os.path.join(DATA_DIR, "customers.csv"),
    "plans":           os.path.join(DATA_DIR, "plans.csv"),
    "subscriptions":   os.path.join(DATA_DIR, "subscriptions.csv"),
    "invoices":        os.path.join(DATA_DIR, "invoices.csv"),
    "support_tickets": os.path.join(DATA_DIR, "support_tickets.csv"),
})

# Define inter-table relationships so the LLM knows how to JOIN the tables
RELATIONSHIPS = [
    {"from_table": "subscriptions",   "from_col": "customer_id",    "to_table": "customers",    "to_col": "customer_id"},
    {"from_table": "subscriptions",   "from_col": "plan_id",         "to_table": "plans",        "to_col": "plan_id"},
    {"from_table": "invoices",        "from_col": "subscription_id", "to_table": "subscriptions","to_col": "subscription_id"},
    {"from_table": "invoices",        "from_col": "customer_id",     "to_table": "customers",    "to_col": "customer_id"},
    {"from_table": "support_tickets", "from_col": "customer_id",     "to_table": "customers",    "to_col": "customer_id"},
]

# Auto-infer schema from DataFrames and inject relationship hints for the LLM
schema = PandasSchemaProvider(
    db,
    relationships=RELATIONSHIPS,
    database_name="cloudmetrics",
    description="CloudMetrics SaaS subscription analytics (loaded from CSV files)",
)

# Create the engine
engine = AskMeDBEngine(
    db=db,
    schema=schema,
    config=AskMeDBConfig(model=os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001")),
)

# Ask a question that requires a JOIN across tables
result = engine.ask("Which plan has the most active subscriptions?")

print(f"Question: {result.question}")
print(f"SQL:      {result.sql}")
print(f"Answer:   {result.answer}")
print(f"Rows:     {result.row_count}")
