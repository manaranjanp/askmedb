# AskMeDB

A Python library for building natural-language database query agents. Ask questions in plain English, get SQL-powered answers.

AskMeDB connects an LLM to your database, generates SQL from natural language, executes it safely, self-corrects on errors, and synthesizes human-readable answers — all in a few lines of code.

## Features

- **Natural Language to SQL** — Converts plain English questions into SQL queries
- **Self-Correction** — Automatically retries and fixes failed SQL queries, learning from mistakes
- **Multi-Turn Conversations** — Follow-up questions maintain context ("Break that down by plan")
- **Multi-Database Support** — SQLite out of the box, PostgreSQL/MySQL/others via SQLAlchemy
- **LLM-Agnostic** — Works with 100+ models via LiteLLM (OpenAI, Anthropic, Groq, Ollama, etc.)
- **Auto Schema Detection** — Introspects your database schema automatically
- **Context Layers** — Enrich prompts with business rules, query patterns, and accumulated learnings
- **Event Hooks** — Monitor the full pipeline (reasoning, SQL generation, corrections, results)
- **Pluggable Architecture** — Extend with custom DB connectors, LLM providers, or schema sources

## Installation

```bash
pip install askmedb
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add askmedb
```

### Optional Dependencies

```bash
# For PostgreSQL, MySQL, and other databases via SQLAlchemy
pip install askmedb[sql]

# For running the included examples
pip install askmedb[examples]
```

## Quick Start

```python
from askmedb import AskMeDBEngine, SQLiteConnector, AutoSchemaProvider

# Connect to your database
db = SQLiteConnector("my_database.db")

# Auto-detect schema
schema = AutoSchemaProvider(db)

# Create the engine and ask a question
engine = AskMeDBEngine(db=db, schema=schema)
result = engine.ask("How many customers do we have?")

print(result.answer)   # "There are 150 customers in the database."
print(result.sql)      # "SELECT COUNT(*) FROM customers"
```

## Configuration

```python
from askmedb import AskMeDBEngine, AskMeDBConfig, SQLiteConnector, AutoSchemaProvider

config = AskMeDBConfig(
    model="anthropic/claude-haiku-4-5-20251001",  # Any LiteLLM-supported model
    sql_temperature=0.0,           # Deterministic SQL generation
    answer_temperature=0.3,        # Slightly creative answers
    max_correction_attempts=3,     # Self-correction retries
    max_conversation_turns=10,     # Multi-turn history window
    max_result_rows=30,            # Rows sent to LLM for answer synthesis
    enable_learnings=True,         # Learn from self-corrections
    learnings_path="learnings.json",  # Persist learnings to file
)

engine = AskMeDBEngine(
    db=SQLiteConnector("my_database.db"),
    schema=AutoSchemaProvider(db),
    config=config,
)
```

## Schema Providers

AskMeDB supports multiple ways to provide your database schema:

```python
from askmedb import AutoSchemaProvider, JSONSchemaProvider, DictSchemaProvider

# Auto-detect from database (easiest)
schema = AutoSchemaProvider(db)

# Load from a JSON file
schema = JSONSchemaProvider("schema.json")

# Pass a dictionary directly
schema = DictSchemaProvider({
    "database": "mydb",
    "tables": [
        {
            "name": "customers",
            "description": "Customer accounts",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "TEXT", "description": "Company name"},
            ],
        }
    ],
})
```

## Enriching Context

Add business rules, query patterns, and a custom agent description for better results:

```python
engine = AskMeDBEngine(
    db=db,
    schema=schema,
    config=config,
    business_rules="business_rules.json",    # Metric definitions and gotchas
    query_patterns="query_patterns.sql",     # Example SQL patterns
    agent_description="You are a data analyst for an e-commerce company.",
)
```

### Business Rules (JSON)

```json
{
  "metrics": [
    {
      "name": "MRR",
      "definition": "Monthly Recurring Revenue — sum of mrr from active subscriptions",
      "sql_hint": "SUM(mrr) FROM subscriptions WHERE status = 'active'"
    }
  ],
  "gotchas": [
    "Always filter subscriptions by status='active' for current metrics",
    "Use DATE() for date comparisons in SQLite"
  ]
}
```

### Query Patterns (SQL)

```sql
-- name: Total MRR
-- keywords: mrr, monthly recurring revenue, total mrr
SELECT SUM(s.mrr) AS total_mrr
FROM subscriptions s
WHERE s.status = 'active';
```

## Multi-Turn Conversations

Follow-up questions automatically reference previous context:

```python
result = engine.ask("What is our total MRR?")
# Answer: "Your total MRR is $45,200."

result = engine.ask("Break that down by plan")
# Answer: "MRR by plan: Starter $5,800, Growth $18,400, Enterprise $21,000"

result = engine.ask("Which plan has the most customers?")
# Answer: "The Starter plan has the most customers with 85 subscriptions."

# Reset conversation when switching topics
engine.reset_conversation()
```

## Event Hooks

Monitor every step of the pipeline:

```python
engine.on_reasoning = lambda r: print(f"Reasoning: {r}")
engine.on_sql_generated = lambda sql: print(f"SQL: {sql}")
engine.on_sql_error = lambda err, sql, attempt: print(f"Error (attempt {attempt}): {err}")
engine.on_sql_corrected = lambda sql, reason: print(f"Corrected: {reason}")
engine.on_results = lambda cols, rows: print(f"Got {len(rows)} rows")
engine.on_warning = lambda w: print(f"Warning: {w}")
engine.on_answer = lambda a: print(f"Answer: {a}")
engine.on_learning_saved = lambda: print("Learned from this correction")
```

## Working with Results

```python
result = engine.ask("Top 5 customers by revenue")

# Access structured data
print(result.question)            # Original question
print(result.sql)                 # Generated SQL
print(result.answer)              # Human-readable answer
print(result.columns)             # Column names
print(result.rows)                # Raw row tuples
print(result.row_count)           # Number of rows
print(result.correction_attempts) # How many retries were needed
print(result.warnings)            # Heuristic warnings

# Convert to pandas DataFrame
df = result.to_dataframe()

# Convert to list of dicts
records = result.to_dicts()
```

## Database Connectors

### SQLite (built-in)

```python
from askmedb import SQLiteConnector

db = SQLiteConnector("path/to/database.db")
```

### SQLAlchemy (PostgreSQL, MySQL, etc.)

```bash
pip install askmedb[sql]
```

```python
from askmedb.db.sqlalchemy_connector import SQLAlchemyConnector

# PostgreSQL
db = SQLAlchemyConnector("postgresql://user:pass@localhost/mydb")

# MySQL
db = SQLAlchemyConnector("mysql+pymysql://user:pass@localhost/mydb")
```

### Custom Connector

```python
from askmedb import BaseDBConnector

class MyConnector(BaseDBConnector):
    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        # Execute SQL, return (column_names, rows)
        ...

    def get_dialect(self) -> str:
        return "postgresql"  # For dialect-specific SQL hints
```

## Custom LLM Provider

```python
from askmedb import BaseLLMProvider

class MyLLMProvider(BaseLLMProvider):
    def generate(self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 2048) -> str:
        # Call your LLM and return the response text
        ...
```

Pass it to the engine:

```python
engine = AskMeDBEngine(db=db, schema=schema, llm=MyLLMProvider())
```

## Running the Examples

The repo includes a sample **CloudMetrics** SaaS database with 5 tables (customers, plans, subscriptions, invoices, support_tickets) and ~200 customers of synthetic data.

### Step 1: Set up the database

```bash
pip install faker
python examples/setup_db.py
```

This creates `examples/cloudmetrics.db` with realistic synthetic data.

### Step 2: Run the quickstart

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install askmedb python-dotenv

python examples/quickstart.py
```

### Step 3: Run the full CLI app (with Rich UI)

```bash
pip install askmedb[examples]

python examples/cloudmetrics/app.py
```

Type questions in plain English, use `samples` to see example queries, or `reset` to clear conversation history.

### Try it on Google Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/manaranjanp/askmedb/blob/main/examples/askmedb_colab_demo.ipynb)

The Colab notebook walks through the full setup: installing dependencies, creating the database, configuring knowledge files, and asking questions interactively.

## Project Structure

```
askmedb/
├── askmedb/                        # Python package
│   ├── core/                       # Engine, config, result, exceptions
│   ├── db/                         # Database connectors (SQLite, SQLAlchemy)
│   ├── llm/                        # LLM providers (LiteLLM)
│   ├── context/                    # Schema, prompt building, context layers
│   └── pipeline/                   # Conversation, parsing, validation, self-correction
├── examples/
│   ├── setup_db.py                 # Creates sample CloudMetrics SQLite database
│   ├── quickstart.py               # Minimal usage example
│   ├── askmedb_colab_demo.ipynb    # Google Colab notebook
│   └── cloudmetrics/               # Full CLI app with Rich UI
│       ├── app.py
│       ├── sample_queries.py
│       └── knowledge/              # Schema, business rules, query patterns
├── pyproject.toml
└── README.md
```

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude models) | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI API key (for GPT models) | `sk-...` |
| `LLM_MODEL` | Override default model | `groq/llama-3.3-70b-versatile` |

Any API key supported by [LiteLLM](https://docs.litellm.ai/docs/providers) works.

## License

MIT
