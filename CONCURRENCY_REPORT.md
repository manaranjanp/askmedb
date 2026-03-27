# AskMeDB Concurrency Feasibility Report

## Executive Summary

AskMeDB was designed as a single-user library. **It is NOT safe for concurrent multi-user access on a shared engine instance.** An application serving multiple users (e.g., a web API, Slack bot, or multi-tenant service) will hit data races in conversation history, learnings persistence, and certain database connectors.

The good news: the fixes are well-scoped. Most issues require adding locks to 2-3 classes. Some concerns (request routing, user isolation, rate limiting) correctly belong at the application layer, not the library.

---

## What Must Change in the Library

### CRITICAL: ConversationManager is not thread-safe

**File:** `askmedb/pipeline/conversation.py`

`ConversationManager._sessions` is a plain dict mutated by `add_turn()`, `get_history()`, `reset()`, and `reset_all()` with no synchronization.

**What breaks:** Two users sharing conversation_id `"default"` will corrupt each other's history — lost turns, interleaved messages, `KeyError` on concurrent reset.

**Fix required:** Add `threading.Lock` around all `_sessions` operations.

```
Thread A: add_turn("user", q1, "default")   ──┐
Thread B: add_turn("user", q2, "default")   ──┤── RACE: both read/write same list
Thread A: get_history("default")             ──┘   returns garbled mix of q1 + q2
```

---

### CRITICAL: SelfCorrector learnings are not thread-safe

**File:** `askmedb/pipeline/correction.py`

`SelfCorrector._learnings` is a plain list. `save_learning()` appends to it AND writes the full list to a JSON file — both without locking.

**What breaks:** Concurrent self-corrections cause list corruption and JSON file corruption (partial writes, truncated JSON).

**Fix required:**
1. `threading.Lock` around `_learnings` reads and writes
2. Atomic file writes (write to temp file, then `os.rename`) to prevent partial JSON on disk

---

### HIGH: Snowflake uses a single shared connection

**File:** `askmedb/db/snowflake_connector.py`

A single `snowflake.connector.Connection` is created at init and reused by all `execute()` calls. The Snowflake Python connector is **not** thread-safe.

**What breaks:** Concurrent queries produce wrong results — one thread's cursor gets overwritten by another's.

**Fix required:** Either:
- Create a new connection per `execute()` call (like SQLiteConnector does), or
- Use a connection pool with thread-local connections

---

### MEDIUM: PandasConnector shares an in-memory SQLite connection

**File:** `askmedb/db/pandas_connector.py`

A single `sqlite3.Connection` to `:memory:` is shared across all `execute()` calls.

**What breaks:** Concurrent queries on the same in-memory database can return corrupted column/row data (cursor state interleaving).

**Fix required:** Add `threading.Lock` around `self._conn.execute()` + `fetchall()` as an atomic unit.

---

### MEDIUM: BigQueryConnector shares client and job_config

**File:** `askmedb/db/bigquery_connector.py`

`self._client` and `self._job_config` are shared. While the BigQuery client is somewhat thread-safe for reads, the shared mutable `QueryJobConfig` is not.

**Fix required:** Create a fresh `QueryJobConfig` per `execute()` call instead of reusing `self._job_config`.

---

### LOW: Event hooks on Engine/FederatedEngine

**Files:** `askmedb/core/engine.py`, `askmedb/core/federated.py`

Callbacks like `on_reasoning`, `on_sql_generated`, etc. are plain attributes. If one thread reassigns a hook while another is invoking it, the behavior is undefined.

**Fix required:** Either document that hooks must be set before any `ask()` calls, or use a lock around hook invocation.

---

## What Does NOT Need to Change in the Library

These are already thread-safe:

| Component | Why It's Safe |
|-----------|--------------|
| `LiteLLMProvider` | Stateless — each `generate()` call is independent, no shared mutable state |
| `SQLiteConnector` | Creates a **new connection per `execute()` call** — each thread gets its own |
| `SQLAlchemyConnector` | Uses SQLAlchemy's built-in `QueuePool` — thread-safe connection pooling |
| `ContextBuilder` | Immutable after `__init__` — all methods are read-only |
| `PromptTemplate` | Immutable after `__init__` |
| `AskMeDBConfig` | Frozen dataclass — no mutations |

---

## What the Application Layer Must Handle (NOT the Library)

### 1. User Isolation — One Engine Per User Session

The library should NOT manage user sessions. The application must create or pool engine instances:

```python
# WRONG — shared engine, conversation history bleeds between users
engine = AskMeDBEngine(db=db, schema=schema)

@app.post("/ask")
def ask(question: str, user_id: str):
    return engine.ask(question, conversation_id=user_id)  # Still shares corrector/learnings!

# RIGHT — engine per session (or pool of engines)
engines: dict[str, AskMeDBEngine] = {}

@app.post("/ask")
def ask(question: str, user_id: str):
    if user_id not in engines:
        engines[user_id] = AskMeDBEngine(db=db, schema=schema)
    return engines[user_id].ask(question)
```

Even after the library's thread-safety fixes, per-user engines provide the cleanest isolation. The library should make this cheap to do (shared DB connector, shared schema, lightweight engine init).

### 2. Rate Limiting and Cost Control

LLM API calls cost money. The library should not enforce rate limits — that's application policy. The application should:
- Limit requests per user per minute
- Set token budgets per user/org
- Queue requests during high load

### 3. Authentication and Authorization

Who can query which database, which tables, which columns — this is application-level access control. The library provides `read_only` mode but has no concept of users or permissions.

### 4. Request Queuing and Timeouts

Long-running queries (BigQuery, Snowflake) can take seconds to minutes. The application must:
- Set query timeouts (not the library's job)
- Use async task queues for heavy queries
- Return partial results or status updates

### 5. Connection Pooling at Scale

For high-concurrency applications (50+ concurrent users), the application should manage a pool of database connections and pass them to the library, rather than relying on the library's built-in connection handling.

### 6. Logging, Monitoring, and Observability

The library provides event hooks (`on_reasoning`, `on_sql_generated`, etc.). The application should wire these to its logging/monitoring stack (Datadog, CloudWatch, etc.).

---

## Recommended Library Changes — Summary

| Priority | Component | Issue | Fix | Effort |
|----------|-----------|-------|-----|--------|
| CRITICAL | `ConversationManager` | Unprotected `_sessions` dict | Add `threading.Lock` | Small |
| CRITICAL | `SelfCorrector` | Unprotected `_learnings` list + file I/O | Add `threading.Lock` + atomic file write | Small |
| HIGH | `SnowflakeConnector` | Single shared connection | Per-call connection or connection pool | Medium |
| MEDIUM | `PandasConnector` | Shared in-memory SQLite connection | Add `threading.Lock` around execute | Small |
| MEDIUM | `BigQueryConnector` | Shared mutable `_job_config` | Create per-call `QueryJobConfig` | Small |
| LOW | Engine event hooks | Mutable callbacks | Document set-before-use, or add lock | Small |

### Total estimated changes: ~100 lines across 5 files

---

## Architecture Recommendation for Multi-User Applications

```
┌─────────────────────────────────────────────┐
│              Application Layer               │
│                                              │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐ │
│  │  Auth &  │  │  Rate    │  │  Request   │ │
│  │  ACL     │  │  Limiter │  │  Queue     │ │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘ │
│       └──────────────┼──────────────┘        │
│                      ▼                       │
│           ┌──────────────────┐               │
│           │  Session Manager │               │
│           │  (engine per     │               │
│           │   user session)  │               │
│           └────────┬─────────┘               │
└────────────────────┼─────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│              AskMeDB Library                 │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  AskMeDBEngine (per user session)    │   │
│  │  ├─ ConversationManager (with lock)  │   │
│  │  ├─ SelfCorrector (with lock)        │   │
│  │  └─ Event hooks                      │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌───────────────────────────────────┐      │
│  │  Shared (thread-safe) resources   │      │
│  │  ├─ DB Connector (with locks)     │      │
│  │  ├─ Schema Provider (immutable)   │      │
│  │  ├─ ContextBuilder (immutable)    │      │
│  │  └─ LiteLLMProvider (stateless)   │      │
│  └───────────────────────────────────┘      │
└─────────────────────────────────────────────┘
```

**Pattern:** Shared DB connector + schema + LLM provider, but **per-user engine instances** for conversation and correction isolation. The library's fixes ensure the shared resources are thread-safe; the application manages user-to-engine mapping.
