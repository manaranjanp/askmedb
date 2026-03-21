"""
AskMeDB Quickstart — Minimal SQLite example.

Usage:
    1. Generate data: python examples/setup_db.py
    2. Set your API key: export ANTHROPIC_API_KEY=...
    3. Run: python examples/sqlite/quickstart.py
"""

import os
import sys

from dotenv import load_dotenv

# Add project root to path so askmedb can be imported without installing
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from askmedb import AskMeDBEngine, AskMeDBConfig, SQLiteConnector, AutoSchemaProvider

# Path to the database bundled with this example
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
db = SQLiteConnector(os.path.join(DATA_DIR, "cloudmetrics.db"))

# Auto-detect schema from the database
schema = AutoSchemaProvider(db, database_name="cloudmetrics", description="SaaS analytics database")

# Create the engine
engine = AskMeDBEngine(
    db=db,
    schema=schema,
    config=AskMeDBConfig(model=os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001")),
)

# Ask a question
result = engine.ask("How many customers do we have?")

print(f"Question: {result.question}")
print(f"SQL:      {result.sql}")
print(f"Answer:   {result.answer}")
print(f"Rows:     {result.row_count}")
