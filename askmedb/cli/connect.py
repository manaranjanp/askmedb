"""Shared database connection utilities for CLI commands."""

import json

DB_TYPES = ["sqlite", "sqlalchemy", "csv", "bigquery", "snowflake"]


def add_db_arguments(parser):
    """Add standard database connection arguments to an argparse parser."""
    parser.add_argument("--db", help="Database path or connection URL (required for sqlite/sqlalchemy)")
    parser.add_argument(
        "--type",
        choices=DB_TYPES,
        default="sqlite",
        help="Database connector type (default: sqlite)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="TABLE=PATH",
        help="CSV/Excel file mappings for --type csv (e.g., customers=data/customers.csv orders=data/orders.csv)",
    )
    parser.add_argument(
        "--csv-relationships",
        help="Path to a JSON file defining relationships between CSV tables",
    )


def connect_db(args):
    """Create a database connector from parsed CLI args.

    Returns:
        A tuple of (connector, schema_provider_or_None).
        For CSV, returns both a PandasConnector and a PandasSchemaProvider.
        For others, returns (connector, None) — schema is handled separately.
    """
    db_type = args.type

    if db_type == "sqlite":
        if not args.db:
            raise ValueError("--db is required for sqlite type")
        from ..db.sqlite import SQLiteConnector
        return SQLiteConnector(db_path=args.db), None

    elif db_type == "sqlalchemy":
        if not args.db:
            raise ValueError("--db is required for sqlalchemy type")
        from ..db.sqlalchemy_connector import SQLAlchemyConnector
        return SQLAlchemyConnector(args.db), None

    elif db_type == "csv":
        if not args.files:
            raise ValueError(
                "--files is required for csv type. "
                "Example: --files customers=data/customers.csv orders=data/orders.csv"
            )
        sources = _parse_file_mappings(args.files)
        from ..db.pandas_connector import PandasConnector
        db = PandasConnector(sources)

        # Build schema with optional relationships
        relationships = None
        if args.csv_relationships:
            with open(args.csv_relationships) as f:
                relationships = json.load(f)

        from ..context.pandas_schema import PandasSchemaProvider
        schema = PandasSchemaProvider(
            sources=db,
            relationships=relationships,
            database_name=args.db or "csv_data",
            description="Data loaded from CSV/Excel files",
        )
        return db, schema

    elif db_type == "bigquery":
        from ..db.bigquery_connector import BigQueryConnector
        return BigQueryConnector(), None

    elif db_type == "snowflake":
        from ..db.snowflake_connector import SnowflakeConnector
        return SnowflakeConnector(), None

    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def _parse_file_mappings(file_args: list[str]) -> dict[str, str]:
    """Parse TABLE=PATH arguments into a dict.

    Also supports plain file paths — the table name is derived from the filename
    (e.g., 'data/customers.csv' -> 'customers').
    """
    sources = {}
    for arg in file_args:
        if "=" in arg:
            table, path = arg.split("=", 1)
            sources[table.strip()] = path.strip()
        else:
            # Derive table name from filename
            from pathlib import Path
            name = Path(arg).stem.lower().replace("-", "_").replace(" ", "_")
            sources[name] = arg
    return sources
