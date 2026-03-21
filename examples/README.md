# AskMeDB Examples

This folder contains runnable examples for the **CloudMetrics** demo dataset — a synthetic B2B SaaS analytics database with customers, subscriptions, invoices, and support tickets.

Two connector flavours are provided side-by-side so you can compare them:

| Folder | Connector | Requires |
|--------|-----------|----------|
| `sqlite/` | `SQLiteConnector` — queries a local `.db` file | `pip install askmedb` |
| `csv/` | `PandasConnector` — loads CSV files into in-memory SQLite | `pip install askmedb[pandas]` |

---

## Prerequisites

### 1. Install the package

From the project root:

```bash
# SQLite examples only
pip install -e .

# CSV/pandas examples
pip install -e ".[pandas]"

# All extras (for the full CLI apps)
pip install -e ".[pandas,examples]"
```

### 2. Set your API key

AskMeDB uses the Anthropic API by default.

```bash
export ANTHROPIC_API_KEY=your-key-here
```

Or add it to a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-key-here
```

---

## SQLite Examples

### Quickstart

Minimal example. Asks one question and prints the result.

```bash
python examples/sqlite/quickstart.py
```

Output:

```
Question: How many customers do we have?
SQL:      SELECT COUNT(*) AS customer_count FROM customers
Answer:   There are 200 customers in the database.
Rows:     1
```

### Full CLI app

Interactive agent with a Rich terminal UI, sample queries, conversation history, and auto-learning.

```bash
python examples/sqlite/cloudmetrics/app.py
```

```
╭─ CloudMetrics Data Agent (SQLite) ──────────────────────╮
│ Powered by AskMeDB | Ask questions about your SaaS data │
│ Type 'help' for commands, 'exit' to quit                 │
╰──────────────────────────────────────────────────────────╯

You> What is our total MRR right now?
```

**Available commands inside the app:**

| Command | Description |
|---------|-------------|
| `help` | Show help and example questions |
| `samples` | List 10 pre-written sample queries |
| `reset` | Clear conversation history |
| `exit` / `quit` | Quit |

The SQLite app uses a hand-crafted `knowledge/` folder with:

- `schema.json` — rich column descriptions and relationships
- `business_rules.json` — metric definitions (MRR, churn rate, ARPU, …)
- `query_patterns.sql` — example SQL patterns for common questions
- `learnings.json` — auto-saved corrections from previous runs

---

## CSV Examples

No database server needed — data is read from CSV files into an in-memory SQLite database at startup.
Relationships between tables are declared explicitly so the LLM can generate correct JOINs.

### Quickstart

```bash
python examples/csv/quickstart.py
```

Output:

```
Question: Which plan has the most active subscriptions?
SQL:      SELECT p.plan_name, COUNT(*) AS active_count
          FROM subscriptions s JOIN plans p ON s.plan_id = p.plan_id
          WHERE s.status = 'active' GROUP BY p.plan_name ORDER BY active_count DESC LIMIT 1
Answer:   The Professional plan has the most active subscriptions.
Rows:     1
```

### Full CLI app

```bash
python examples/csv/cloudmetrics/app.py
```

```
╭─ CloudMetrics Data Agent (CSV) ─────────────────────────╮
│ Powered by AskMeDB | Ask questions about your SaaS data │
│ Type 'help' for commands, 'exit' to quit                 │
╰──────────────────────────────────────────────────────────╯

Loading CSV files...
Ready.

You>
```

The CSV app auto-infers the schema from the DataFrame column types and injects the following relationship hints so cross-table JOINs work correctly:

| From table | Foreign key | References |
|------------|-------------|------------|
| `subscriptions` | `customer_id` | `customers.customer_id` |
| `subscriptions` | `plan_id` | `plans.plan_id` |
| `invoices` | `subscription_id` | `subscriptions.subscription_id` |
| `invoices` | `customer_id` | `customers.customer_id` |
| `support_tickets` | `customer_id` | `customers.customer_id` |

---

## Sample Queries to Try

```
How many customers do we have?
What are our plan names and prices?
What is our total MRR right now?
Show me the number of customers by industry
Which plan has the most active subscriptions?
What is the monthly revenue trend for the last 12 months?
Which industry has the highest average MRR per customer?
What is the average support ticket resolution time in hours, broken down by priority?
Show me the top 5 customers by total revenue who have also filed more than 3 support tickets
What is the monthly churn rate over the past 6 months?
```

Follow-up questions also work (conversation history is preserved):

```
You> What is our total MRR?
You> Break that down by plan
You> Now show only annual billing
```

---

## Folder Structure

```
examples/
  sqlite/
    data/
      cloudmetrics.db          ← SQLite database
    quickstart.py              ← minimal SQLite example
    cloudmetrics/
      app.py                   ← interactive CLI (SQLite)
      sample_queries.py
      knowledge/
        schema.json            ← table/column descriptions
        business_rules.json    ← metric definitions
        query_patterns.sql     ← example SQL patterns
        learnings.json         ← auto-saved corrections
  csv/
    data/
      customers.csv
      plans.csv
      subscriptions.csv
      invoices.csv
      support_tickets.csv
    quickstart.py              ← minimal CSV example
    cloudmetrics/
      app.py                   ← interactive CLI (CSV)
      sample_queries.py
  askmedb_colab_demo.ipynb     ← Google Colab notebook
```

---

## Choosing Between SQLite and CSV

| | SQLite | CSV |
|-|--------|-----|
| **Schema quality** | Hand-crafted JSON with descriptions | Auto-inferred from column types |
| **Business rules** | `business_rules.json` provides metric hints | Not included (add via `PandasSchemaProvider`) |
| **Data persistence** | Rows survive restarts | Reloaded from CSV on each run |
| **Best for** | Production-like setup with curated schema | Ad-hoc analysis of flat files |
