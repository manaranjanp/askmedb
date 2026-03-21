"""Schema provider that infers metadata from pandas DataFrames."""

from .schema import SchemaProvider


# Maps pandas dtype strings to SQL type labels shown to the LLM
_DTYPE_TO_SQL = {
    "int8":          "INTEGER",
    "int16":         "INTEGER",
    "int32":         "INTEGER",
    "int64":         "INTEGER",
    "uint8":         "INTEGER",
    "uint16":        "INTEGER",
    "uint32":        "INTEGER",
    "uint64":        "INTEGER",
    "float16":       "FLOAT",
    "float32":       "FLOAT",
    "float64":       "FLOAT",
    "bool":          "BOOLEAN",
    "datetime64[ns]":"DATETIME",
    "object":        "TEXT",
    "string":        "TEXT",
    "category":      "TEXT",
}


class PandasSchemaProvider(SchemaProvider):
    """Build a schema dict by inspecting pandas DataFrames.

    Relationship hints must be supplied explicitly because CSV/Excel files carry
    no foreign-key constraints.  Without them the LLM cannot produce JOINs.

    Args:
        sources: Either a ``PandasConnector`` instance (the provider reads
                 ``connector.dataframes`` automatically) or a plain
                 ``{table_name: DataFrame}`` dict.
        relationships: List of dicts describing inter-table links::

                [
                    {
                        "from_table": "orders",
                        "from_col":   "customer_id",
                        "to_table":   "customers",
                        "to_col":     "customer_id",
                    },
                    ...
                ]

        database_name: Label used in the schema header shown to the LLM.
        description: Optional human-readable description of the dataset.

    Example::

        from askmedb.db.pandas_connector import PandasConnector
        from askmedb.context.pandas_schema import PandasSchemaProvider

        db = PandasConnector({"customers": "customers.csv", "orders": "orders.csv"})

        schema = PandasSchemaProvider(
            sources=db,
            relationships=[
                {"from_table": "orders", "from_col": "customer_id",
                 "to_table": "customers", "to_col": "customer_id"},
            ],
            database_name="ecommerce",
            description="E-commerce order data loaded from CSV exports",
        )
    """

    def __init__(
        self,
        sources,
        relationships: list[dict] | None = None,
        database_name: str = "data",
        description: str = "",
    ):
        # Accept either a PandasConnector or a plain dict of DataFrames
        if hasattr(sources, "dataframes"):
            self._dataframes = sources.dataframes
        elif isinstance(sources, dict):
            self._dataframes = sources
        else:
            raise TypeError(
                "sources must be a PandasConnector instance or a dict of DataFrames."
            )

        self._relationships = relationships or []
        self._database_name = database_name
        self._description = description

    def get_schema(self) -> dict:
        """Build and return the schema dict in AskMeDB format."""
        rels_by_table: dict[str, list] = {}
        for rel in self._relationships:
            rels_by_table.setdefault(rel["from_table"], []).append(rel)

        tables = []
        for table_name, df in self._dataframes.items():
            columns = []
            for col_name, dtype in df.dtypes.items():
                sql_type = _DTYPE_TO_SQL.get(str(dtype), "TEXT")
                # Refine object columns that look like dates
                if sql_type == "TEXT":
                    sample = df[col_name].dropna().head(5).astype(str).tolist()
                    if _looks_like_date(sample):
                        sql_type = "DATE"

                columns.append({
                    "name": col_name,
                    "type": sql_type,
                    "description": "",
                    "primary_key": False,
                })

            table_rels = [
                {
                    "column": r["from_col"],
                    "references": f"{r['to_table']}.{r['to_col']}",
                    "type": "many-to-one",
                }
                for r in rels_by_table.get(table_name, [])
            ]

            tables.append({
                "name": table_name,
                "description": f"{len(df):,} rows loaded from source file",
                "columns": columns,
                "relationships": table_rels or None,
            })

        return {
            "database": self._database_name,
            "description": self._description,
            "tables": tables,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

import re

_DATE_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}$",          # 2024-01-15
    r"^\d{2}/\d{2}/\d{4}$",           # 01/15/2024
    r"^\d{4}-\d{2}-\d{2}T\d{2}:",     # ISO datetime
]


def _looks_like_date(samples: list[str]) -> bool:
    """Return True if the majority of non-empty samples look like date strings."""
    if not samples:
        return False
    hits = sum(
        1 for s in samples
        if any(re.match(pat, s) for pat in _DATE_PATTERNS)
    )
    return hits >= len(samples) / 2
