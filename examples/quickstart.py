"""
AskDB Quickstart — Minimal example showing library usage.

Usage:
    1. Set your API key: export ANTHROPIC_API_KEY=...
    2. Run: python askdb/examples/quickstart.py
"""

import os
import sys

from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, PROJECT_ROOT)
load_dotenv()

from askdb import AskDBEngine, AskDBConfig, SQLiteConnector, AutoSchemaProvider

# Create a connector for your database
db = SQLiteConnector(os.path.join(PROJECT_ROOT, "cloudmetrics.db"))

# Auto-detect schema from the database
schema = AutoSchemaProvider(db, database_name="cloudmetrics", description="SaaS analytics database")

# Create the engine
engine = AskDBEngine(
    db=db,
    schema=schema,
    config=AskDBConfig(model=os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001")),
)

# Ask a question
result = engine.ask("How many customers do we have?")

print(f"Question: {result.question}")
print(f"SQL:      {result.sql}")
print(f"Answer:   {result.answer}")
print(f"Rows:     {result.row_count}")
