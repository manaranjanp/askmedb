"""Serve CLI command — start AskMeDB as an MCP server."""

from ..core.config import AskMeDBConfig
from .connect import add_db_arguments, connect_db


def register(subparsers):
    """Register the serve subcommand."""
    p = subparsers.add_parser(
        "serve",
        help="Start AskMeDB as an MCP server",
    )
    add_db_arguments(p)
    p.add_argument("--schema", help="Path to schema.json file (optional, auto-detected if omitted)")
    p.add_argument("--business-rules", help="Path to business_rules.json file")
    p.add_argument("--query-patterns", help="Path to query_patterns.sql file")
    p.add_argument("--model", default=AskMeDBConfig.model, help="LLM model to use")
    p.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    p.add_argument(
        "--allow-write",
        action="store_true",
        default=False,
        help="Disable read-only mode (allows execute_sql tool for mutations)",
    )
    p.set_defaults(func=run_serve)


def run_serve(args):
    """Execute the serve command."""
    db, csv_schema = connect_db(args)

    # Set up schema: explicit --schema flag > CSV auto-schema > AutoSchemaProvider
    if args.schema:
        from ..context.schema import JSONSchemaProvider
        schema = JSONSchemaProvider(args.schema)
    elif csv_schema:
        schema = csv_schema
    else:
        from ..context.schema import AutoSchemaProvider
        schema = AutoSchemaProvider(db)

    config = AskMeDBConfig(
        model=args.model,
        read_only=not args.allow_write,
    )

    from ..mcp.server import create_server

    mcp = create_server(
        db=db,
        schema=schema,
        config=config,
        business_rules=args.business_rules,
        query_patterns=args.query_patterns,
    )

    mcp.run(transport=args.transport)
