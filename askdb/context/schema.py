"""Schema providers for loading database metadata."""

import json
from abc import ABC, abstractmethod

from ..core.exceptions import SchemaError


class SchemaProvider(ABC):
    """Abstract base for schema metadata sources."""

    @abstractmethod
    def get_schema(self) -> dict:
        """Return schema dict in AskDB format.

        Expected format:
            {
                "database": "name",
                "description": "...",
                "tables": [
                    {
                        "name": "table_name",
                        "description": "...",
                        "columns": [
                            {"name": "col", "type": "TEXT", "description": "...", "primary_key": true}
                        ],
                        "relationships": [
                            {"column": "col", "references": "other.col", "type": "many-to-one"}
                        ]
                    }
                ]
            }
        """
        ...

    def format_schema(self) -> str:
        """Format the schema into a readable string for LLM context."""
        schema = self.get_schema()
        lines = []

        if schema.get("database"):
            lines.append(f"Database: {schema['database']}")
        if schema.get("description"):
            lines.append(f"Description: {schema['description']}")
        lines.append("")

        for table in schema.get("tables", []):
            lines.append(f"Table: {table['name']}")
            if table.get("description"):
                lines.append(f"  Description: {table['description']}")
            lines.append("  Columns:")
            for col in table.get("columns", []):
                pk = " [PRIMARY KEY]" if col.get("primary_key") else ""
                desc = f": {col['description']}" if col.get("description") else ""
                lines.append(f"    - {col['name']} ({col.get('type', 'UNKNOWN')}){pk}{desc}")
            if table.get("relationships"):
                lines.append("  Relationships:")
                for rel in table["relationships"]:
                    lines.append(f"    - {rel['column']} -> {rel['references']} ({rel['type']})")
            lines.append("")

        return "\n".join(lines)


class JSONSchemaProvider(SchemaProvider):
    """Load schema from a JSON file.

    Args:
        path: Path to the schema JSON file.
    """

    def __init__(self, path: str):
        self.path = path

    def get_schema(self) -> dict:
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise SchemaError(f"Failed to load schema from {self.path}: {e}") from e


class DictSchemaProvider(SchemaProvider):
    """Use a pre-built dictionary as schema.

    Args:
        schema: Schema dictionary in AskDB format.
    """

    def __init__(self, schema: dict):
        self._schema = schema

    def get_schema(self) -> dict:
        return self._schema


class AutoSchemaProvider(SchemaProvider):
    """Auto-detect schema by introspecting the database.

    Works with SQLite databases and SQLAlchemy-backed databases.

    Args:
        db: A database connector instance to introspect.
        database_name: Optional name for the database in the schema.
        description: Optional description for the database.
    """

    def __init__(self, db, database_name: str = "database", description: str = ""):
        self.db = db
        self.database_name = database_name
        self.description = description

    def get_schema(self) -> dict:
        dialect = self.db.get_dialect()
        if dialect == "sqlite":
            return self._introspect_sqlite()
        else:
            return self._introspect_sqlalchemy()

    def _introspect_sqlite(self) -> dict:
        """Introspect a SQLite database."""
        tables = []

        # Get table names
        cols, rows = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        table_names = [row[0] for row in rows]

        for table_name in table_names:
            # Get column info
            cols, rows = self.db.execute(f"PRAGMA table_info('{table_name}')")
            columns = []
            for row in rows:
                # row: (cid, name, type, notnull, dflt_value, pk)
                columns.append({
                    "name": row[1],
                    "type": row[2] or "TEXT",
                    "description": "",
                    "primary_key": bool(row[5]),
                })

            # Get foreign keys
            fk_cols, fk_rows = self.db.execute(f"PRAGMA foreign_key_list('{table_name}')")
            relationships = []
            for fk in fk_rows:
                # fk: (id, seq, table, from, to, on_update, on_delete, match)
                relationships.append({
                    "column": fk[3],
                    "references": f"{fk[2]}.{fk[4]}",
                    "type": "many-to-one",
                })

            tables.append({
                "name": table_name,
                "description": "",
                "columns": columns,
                "relationships": relationships if relationships else None,
            })

        return {
            "database": self.database_name,
            "description": self.description,
            "tables": tables,
        }

    def _introspect_sqlalchemy(self) -> dict:
        """Introspect using SQLAlchemy inspect."""
        try:
            from sqlalchemy import inspect
        except ImportError:
            raise SchemaError("SQLAlchemy is required for auto-schema with non-SQLite databases.")

        inspector = inspect(self.db.engine)
        tables = []

        for table_name in inspector.get_table_names():
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "description": col.get("comment", "") or "",
                    "primary_key": col.get("name") in [
                        pk["name"] for pk in inspector.get_pk_constraint(table_name).get("constrained_columns", [])
                    ] if isinstance(inspector.get_pk_constraint(table_name).get("constrained_columns"), list) else False,
                })

            relationships = []
            for fk in inspector.get_foreign_keys(table_name):
                for local_col, remote_col in zip(
                    fk["constrained_columns"], fk["referred_columns"]
                ):
                    relationships.append({
                        "column": local_col,
                        "references": f"{fk['referred_table']}.{remote_col}",
                        "type": "many-to-one",
                    })

            tables.append({
                "name": table_name,
                "description": "",
                "columns": columns,
                "relationships": relationships if relationships else None,
            })

        return {
            "database": self.database_name,
            "description": self.description,
            "tables": tables,
        }
