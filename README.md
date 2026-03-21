# AskMeDB

A Python library for building natural-language database query agents. Ask questions in plain English, get SQL-powered answers.

AskMeDB connects an LLM to your database, generates SQL from natural language, executes it safely, self-corrects on errors, and synthesizes human-readable answers — all in a few lines of code.

## Features

- **Natural Language to SQL** — Converts plain English questions into SQL queries
- **Self-Correction** — Automatically retries and fixes failed SQL queries, learning from mistakes
- **Multi-Turn Conversations** — Follow-up questions maintain context ("Break that down by plan")
- **Multi-Database Support** — SQLite, PostgreSQL, MySQL, Google BigQuery, Snowflake, CSV/Excel files, and any SQLAlchemy-compatible database
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
# PostgreSQL, MySQL, and other databases via SQLAlchemy
pip install askmedb[sql]

# CSV and Excel file support via pandas
pip install askmedb[pandas]

# Google BigQuery
pip install askmedb[bigquery]

# Snowflake
pip install askmedb[snowflake]

# All connectors at once
pip install askmedb[all]

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

## Design & Architecture

### The Inspiration

> *"Our data agent lets employees go from question to insight in minutes, not days. This lowers the bar to pulling data and nuanced analysis across all functions, not just by our data team."*
> — OpenAI's Blog

OpenAI's agent operates across 70,000 datasets, uses GPT-5 for reasoning, and features six layers of context enrichment including code-level table understanding, institutional knowledge from Slack and Docs, and a self-learning memory system.

AskMeDB captures the core concepts in a **minimal, self-contained library** anyone can run locally:

- A realistic business use case with 4–5 related tables
- Context-grounded SQL generation (not naive text-to-SQL)
- A self-correction loop that fixes broken queries
- A learning system that remembers past mistakes
- A conversational interface that supports follow-up questions

### Architecture: The 4-Layer Context Model

The single biggest lesson from OpenAI's blog is that **context is everything**. A raw LLM given just "What is our MRR?" and a database schema will generate plausible-looking but often incorrect SQL. AskMeDB uses four layers of context assembled into every LLM call:

![4-Layer Context Model](layers.jpg)

### The Agent Loop

Every question passes through this flow. Two LLM calls per question: one to generate SQL (deterministic, temperature=0.0), and one to synthesize a human-readable answer from the results (slightly creative, temperature=0.3). If the SQL fails, the self-correction loop adds up to 3 more LLM calls to fix it.

![Agent Loop](agent.jpg)

## Advanced Usage

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

# Load from a JSON file (see example below)
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

### Example `schema.json`

The JSON schema file describes your database structure, including table descriptions, column types, and relationships. Here's a trimmed example from the included CloudMetrics demo:

```json
{
  "database": "cloudmetrics.db",
  "description": "CloudMetrics SaaS subscription analytics database.",
  "tables": [
    {
      "name": "customers",
      "description": "All registered customer companies.",
      "columns": [
        {"name": "customer_id", "type": "INTEGER", "description": "Unique customer identifier", "primary_key": true},
        {"name": "company_name", "type": "TEXT", "description": "Registered company name"},
        {"name": "industry", "type": "TEXT", "description": "Industry vertical. One of: Technology, Healthcare, Finance, Retail, Education, Manufacturing"},
        {"name": "signup_date", "type": "DATE", "description": "Date the customer first signed up (YYYY-MM-DD format)"}
      ],
      "relationships": [
        {"column": "customer_id", "references": "subscriptions.customer_id", "type": "one-to-many"}
      ]
    },
    {
      "name": "subscriptions",
      "description": "Customer subscriptions to plans.",
      "columns": [
        {"name": "subscription_id", "type": "INTEGER", "description": "Unique subscription identifier", "primary_key": true},
        {"name": "customer_id", "type": "INTEGER", "description": "Foreign key to customers table"},
        {"name": "plan_id", "type": "INTEGER", "description": "Foreign key to plans table"},
        {"name": "status", "type": "TEXT", "description": "One of: active, churned, trial, paused"},
        {"name": "mrr", "type": "REAL", "description": "Monthly Recurring Revenue in USD"}
      ],
      "relationships": [
        {"column": "customer_id", "references": "customers.customer_id", "type": "many-to-one"},
        {"column": "plan_id", "references": "plans.plan_id", "type": "many-to-one"}
      ]
    }
  ]
}
```

The full schema file is at [`examples/cloudmetrics/knowledge/schema.json`](examples/cloudmetrics/knowledge/schema.json).

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

AskMeDB supports six connector types out of the box. All credentials are read from **environment variables** — never hardcode secrets in source code. Constructor arguments are optional overrides for testing.

| Connector | Install extra | Credential env vars |
|---|---|---|
| `SQLiteConnector` | *(built-in)* | `SQLITE_DB_PATH` |
| `SQLAlchemyConnector` | `askmedb[sql]` | `DATABASE_URL` |
| `PandasConnector` | `askmedb[pandas]` | *(none — reads local files)* |
| `BigQueryConnector` | `askmedb[bigquery]` | `BIGQUERY_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| `SnowflakeConnector` | `askmedb[snowflake]` | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, … |

---

### SQLite (built-in)

SQLite is a file-based, embedded database — no server, no user accounts, no password. Only the file path is needed.

**Environment variable:**

```bash
SQLITE_DB_PATH=/data/mydb.sqlite
```

**Usage:**

```python
from askmedb import SQLiteConnector

# Path from environment variable (recommended)
db = SQLiteConnector()

# Explicit path override
db = SQLiteConnector(db_path="/data/mydb.sqlite")
```

---

### SQLAlchemy — PostgreSQL, MySQL, MS SQL, Oracle

Supports any SQLAlchemy-compatible database via a single connection URL. The URL encodes the driver, credentials, host, port, and database name.

```bash
pip install askmedb[sql]
```

**Environment variable:**

```bash
# PostgreSQL
DATABASE_URL=postgresql://alice:s3cr3t@prod-db.internal:5432/analytics

# MySQL
DATABASE_URL=mysql+pymysql://root:pass@localhost:3306/mydb

# SQLite via SQLAlchemy
DATABASE_URL=sqlite:///./local.db

# MS SQL Server
DATABASE_URL=mssql+pyodbc://user:pass@host/dbname?driver=ODBC+Driver+17+for+SQL+Server

# Oracle
DATABASE_URL=oracle+cx_oracle://user:pass@host:1521/service
```

**Usage:**

```python
from askmedb.db.sqlalchemy_connector import SQLAlchemyConnector

# Connection string from DATABASE_URL env var (recommended)
db = SQLAlchemyConnector()

# Explicit override
db = SQLAlchemyConnector("postgresql://alice:s3cr3t@localhost/analytics")

engine = AskMeDBEngine(db=db, schema="auto")
```

---

### CSV and Excel Files (pandas bridge)

Loads one or more CSV/Excel files into an in-memory SQLite database so standard SQL — including cross-file JOINs — works transparently. Column names are normalised (lowercased, spaces → underscores) automatically.

```bash
pip install askmedb[pandas]
```

**No credentials required** — sources are local file paths.

**Usage:**

```python
from askmedb import AskMeDBEngine, PandasSchemaProvider
from askmedb.db.pandas_connector import PandasConnector

# Load multiple related files
db = PandasConnector({
    "customers":   "data/customers.csv",
    "orders":      "data/orders.csv",
    "order_items": "data/order_items.xlsx",  # Excel supported
})

# Describe relationships explicitly (CSV has no foreign keys)
schema = PandasSchemaProvider(
    sources=db,
    relationships=[
        {"from_table": "orders",      "from_col": "customer_id",
         "to_table":   "customers",   "to_col":   "customer_id"},
        {"from_table": "order_items", "from_col": "order_id",
         "to_table":   "orders",      "to_col":   "order_id"},
    ],
    database_name="ecommerce",
    description="E-commerce data loaded from CSV exports",
)

engine = AskMeDBEngine(db=db, schema=schema)
result = engine.ask("Top 5 customers by total revenue this year")
```

> **Why describe relationships manually?**
> CSV and Excel files carry no foreign-key metadata. Without relationship hints the LLM cannot produce correct JOIN queries across files. The `PandasSchemaProvider` passes this information into the prompt alongside the auto-detected column types.

---

### Google BigQuery

Runs queries against BigQuery using the native `google-cloud-bigquery` client.

```bash
pip install askmedb[bigquery]
```

**Authentication options (choose one):**

| Method | How to configure |
|---|---|
| Service account key file | Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of the JSON key |
| Application Default Credentials | Run `gcloud auth application-default login` on your machine |
| Workload Identity / GCE | Automatic when running on GCP infrastructure (Cloud Run, GKE, etc.) |

**Environment variables:**

```bash
# Required
BIGQUERY_PROJECT_ID=my-gcp-project

# Required unless using ADC or running on GCP infrastructure
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json

# Optional
BIGQUERY_LOCATION=US          # processing region, default "US"
BIGQUERY_DATASET=analytics    # default dataset for unqualified table names
```

**Usage:**

```python
from askmedb.db.bigquery_connector import BigQueryConnector
from askmedb import AskMeDBEngine, AutoSchemaProvider

# All config from environment variables (recommended)
db = BigQueryConnector()

# Override specific values
db = BigQueryConnector(project_id="my-gcp-project", location="EU")

engine = AskMeDBEngine(db=db, schema=AutoSchemaProvider(db))
result = engine.ask("What was total revenue by region last quarter?")
```

---

### Snowflake

Runs queries against Snowflake using the native `snowflake-connector-python` client.

```bash
pip install askmedb[snowflake]
```

**Authentication options (choose one):**

| Method | Environment variable(s) |
|---|---|
| Username + password | `SNOWFLAKE_PASSWORD` |
| Key-pair (more secure) | `SNOWFLAKE_PRIVATE_KEY_PATH` + optionally `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` |

**Environment variables:**

```bash
# Required
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=analyst
SNOWFLAKE_DATABASE=ANALYTICS
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# Authentication — set one of:
SNOWFLAKE_PASSWORD=s3cr3t
SNOWFLAKE_PRIVATE_KEY_PATH=/secrets/rsa_key.pem
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=key_passphrase   # only if key is encrypted

# Optional
SNOWFLAKE_ROLE=ANALYST_ROLE
```

**Usage:**

```python
from askmedb.db.snowflake_connector import SnowflakeConnector
from askmedb import AskMeDBEngine, AutoSchemaProvider

# All config from environment variables (recommended)
db = SnowflakeConnector()

# Override specific values (e.g. point at a staging schema)
db = SnowflakeConnector(database="STAGING", schema="RAW")

engine = AskMeDBEngine(db=db, schema=AutoSchemaProvider(db))
result = engine.ask("Which accounts had the highest usage last month?")
```

---

### Custom Connector

Implement `BaseDBConnector` to connect AskMeDB to any data source — a REST API, a proprietary database, or a custom query engine.

```python
from askmedb import BaseDBConnector

class MyConnector(BaseDBConnector):
    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        # Run the query, return (column_name_list, row_tuples)
        ...

    def get_dialect(self) -> str:
        # Return the SQL dialect for prompt hints
        # Known values: "sqlite", "postgresql", "mysql", "bigquery", "snowflake"
        return "postgresql"
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
│   ├── db/                         # Database connectors (SQLite, SQLAlchemy, Pandas, BigQuery, Snowflake)
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

### LLM API Keys

| Variable | Description | Example |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude models) | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI API key (for GPT models) | `sk-...` |
| `LLM_MODEL` | Override default model | `groq/llama-3.3-70b-versatile` |

Any API key supported by [LiteLLM](https://docs.litellm.ai/docs/providers) works.

### Database Connector Variables

#### SQLite

| Variable | Required | Description | Example |
|---|---|---|---|
| `SQLITE_DB_PATH` | Yes | Path to the SQLite database file | `/data/mydb.sqlite` |

#### SQLAlchemy (PostgreSQL, MySQL, MS SQL, Oracle)

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | Yes | Full SQLAlchemy connection URL including credentials | `postgresql://user:pass@host:5432/db` |

#### Google BigQuery

| Variable | Required | Description | Example |
|---|---|---|---|
| `BIGQUERY_PROJECT_ID` | Yes | GCP project billed for queries | `my-gcp-project` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes* | Path to service-account JSON key file | `/secrets/sa.json` |
| `BIGQUERY_LOCATION` | No | Processing region (default: `US`) | `EU` |
| `BIGQUERY_DATASET` | No | Default dataset for unqualified table names | `analytics` |

*Not required when using Application Default Credentials (`gcloud auth application-default login`) or running on GCP infrastructure.

#### Snowflake

| Variable | Required | Description | Example |
|---|---|---|---|
| `SNOWFLAKE_ACCOUNT` | Yes | Account identifier | `xy12345.us-east-1` |
| `SNOWFLAKE_USER` | Yes | Snowflake username | `analyst` |
| `SNOWFLAKE_DATABASE` | Yes | Default database | `ANALYTICS` |
| `SNOWFLAKE_SCHEMA` | Yes | Default schema | `PUBLIC` |
| `SNOWFLAKE_WAREHOUSE` | Yes | Compute warehouse | `COMPUTE_WH` |
| `SNOWFLAKE_PASSWORD` | Yes* | Password for username/password auth | `s3cr3t` |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | Yes* | Path to PEM private key for key-pair auth | `/secrets/rsa_key.pem` |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | No | Passphrase if private key is encrypted | `key_pass` |
| `SNOWFLAKE_ROLE` | No | Snowflake role to assume | `ANALYST_ROLE` |

*Either `SNOWFLAKE_PASSWORD` or `SNOWFLAKE_PRIVATE_KEY_PATH` must be set.

## License

MIT
