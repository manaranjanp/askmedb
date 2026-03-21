"""Pandas bridge connector — load CSV/Excel files into an in-memory SQLite database."""

import sqlite3
from pathlib import Path

from .base import BaseDBConnector


class PandasConnector(BaseDBConnector):
    """Load CSV and Excel files as SQL tables backed by an in-memory SQLite database.

    Each key in *sources* becomes a table name. Values can be file paths (str or
    Path) or pre-built pandas DataFrames.  Multiple files are loaded into the
    same in-memory database so cross-file JOINs work transparently.

    Column names are normalised (stripped, lowercased, spaces → underscores) so
    the LLM always sees clean, predictable identifiers.

    Args:
        sources: Mapping of ``{table_name: file_path_or_dataframe}``.
                 Supported file types: ``.csv``, ``.tsv``, ``.xlsx``, ``.xls``.
        sheet_name: Sheet to read from Excel files (default 0 = first sheet).
                    Pass a sheet name string to target a specific sheet.

    Example::

        from askmedb.db.pandas_connector import PandasConnector

        db = PandasConnector({
            "customers":   "data/customers.csv",
            "orders":      "data/orders.csv",
            "order_items": "data/order_items.xlsx",
        })
    """

    def __init__(self, sources: dict, sheet_name: int | str = 0):
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for PandasConnector. "
                "Install it with: pip install askmedb[pandas]"
            ) from None

        self._conn = sqlite3.connect(":memory:")
        self._dataframes: dict = {}

        for table_name, source in sources.items():
            if isinstance(source, pd.DataFrame):
                df = source.copy()
            else:
                path = str(source)
                suffix = Path(path).suffix.lower()
                if suffix in (".xlsx", ".xls"):
                    try:
                        df = pd.read_excel(path, sheet_name=sheet_name)
                    except ImportError:
                        raise ImportError(
                            "openpyxl is required to read Excel files. "
                            "Install it with: pip install askmedb[pandas]"
                        ) from None
                elif suffix == ".tsv":
                    df = pd.read_csv(path, sep="\t")
                else:
                    df = pd.read_csv(path)

            df = self._normalise_columns(df)
            df.to_sql(table_name, self._conn, if_exists="replace", index=False)
            self._dataframes[table_name] = df

    # ------------------------------------------------------------------
    # BaseDBConnector interface
    # ------------------------------------------------------------------

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query against the in-memory SQLite database."""
        cursor = self._conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def get_dialect(self) -> str:
        return "sqlite"

    def close(self):
        self._conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def dataframes(self) -> dict:
        """Return the loaded DataFrames keyed by table name (read-only copy)."""
        return dict(self._dataframes)

    @staticmethod
    def _normalise_columns(df):
        """Strip, lowercase, and replace spaces/special chars in column names."""
        df = df.copy()
        df.columns = [
            col.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
            for col in df.columns
        ]
        return df
