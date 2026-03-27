"""MCP server implementation for AskMeDB."""

from mcp.server.fastmcp import FastMCP

from ..core.config import AskMeDBConfig
from ..core.engine import AskMeDBEngine
from ..db.base import BaseDBConnector
from ..context.schema import SchemaProvider


def create_server(
    db: BaseDBConnector,
    schema: SchemaProvider | dict | str,
    config: AskMeDBConfig | None = None,
    business_rules: str | dict | None = None,
    query_patterns: str | None = None,
    server_name: str = "askmedb",
) -> FastMCP:
    """Create an MCP server wrapping an AskMeDB engine.

    Args:
        db: Database connector instance.
        schema: Schema provider, dict, or path to schema.json.
        config: Engine configuration. Defaults to read_only=True.
        business_rules: Optional business rules.
        query_patterns: Optional query patterns.
        server_name: MCP server name.

    Returns:
        A configured FastMCP server instance.
    """
    if config is None:
        config = AskMeDBConfig(read_only=True)

    engine = AskMeDBEngine(
        db=db,
        schema=schema,
        config=config,
        business_rules=business_rules,
        query_patterns=query_patterns,
    )

    mcp = FastMCP(server_name)

    @mcp.tool()
    def ask(question: str) -> dict:
        """Ask a natural-language question about the database. Returns the answer, generated SQL, and result data."""
        result = engine.ask(question)
        return {
            "answer": result.answer,
            "sql": result.sql,
            "columns": result.columns,
            "rows": [list(row) for row in result.rows[:config.max_result_rows]],
            "success": result.success,
            "error": result.error,
            "correction_attempts": result.correction_attempts,
        }

    @mcp.tool()
    def list_tables() -> dict:
        """List all tables in the database with their descriptions."""
        if isinstance(schema, SchemaProvider):
            schema_dict = schema.get_schema()
        elif isinstance(schema, dict):
            schema_dict = schema
        else:
            from ..context.schema import JSONSchemaProvider
            schema_dict = JSONSchemaProvider(schema).get_schema()

        tables = []
        for table in schema_dict.get("tables", []):
            tables.append({
                "name": table.get("name", ""),
                "description": table.get("description", ""),
                "column_count": len(table.get("columns", [])),
            })
        return {"tables": tables}

    @mcp.tool()
    def get_schema() -> dict:
        """Get the full database schema as JSON, including tables, columns, types, and relationships."""
        if isinstance(schema, SchemaProvider):
            return schema.get_schema()
        elif isinstance(schema, dict):
            return schema
        else:
            from ..context.schema import JSONSchemaProvider
            return JSONSchemaProvider(schema).get_schema()

    if not config.read_only:
        @mcp.tool()
        def execute_sql(sql: str) -> dict:
            """Execute a raw SQL query against the database. Only available when read_only is disabled."""
            try:
                columns, rows = db.execute(sql)
                return {
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows),
                    "success": True,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

    @mcp.tool()
    def reset_conversation() -> dict:
        """Reset the conversation history, clearing all context from previous questions."""
        engine.reset_conversation()
        return {"status": "conversation reset"}

    return mcp
