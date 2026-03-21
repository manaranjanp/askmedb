"""Snowflake connector for AskMeDB."""

import os

from .base import BaseDBConnector


# Environment variables read by this connector
_ENV_ACCOUNT     = "SNOWFLAKE_ACCOUNT"
_ENV_USER        = "SNOWFLAKE_USER"
_ENV_PASSWORD    = "SNOWFLAKE_PASSWORD"
_ENV_DATABASE    = "SNOWFLAKE_DATABASE"
_ENV_SCHEMA      = "SNOWFLAKE_SCHEMA"
_ENV_WAREHOUSE   = "SNOWFLAKE_WAREHOUSE"
_ENV_ROLE        = "SNOWFLAKE_ROLE"
_ENV_PRIVATE_KEY = "SNOWFLAKE_PRIVATE_KEY_PATH"
_ENV_PK_PASS     = "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"


class SnowflakeConnector(BaseDBConnector):
    """Execute SQL queries against Snowflake.

    All connection parameters are read from **environment variables** by default.
    Constructor arguments are optional overrides — useful for testing or when
    managing multiple connections in the same process.

    Required environment variables
    --------------------------------
    ``SNOWFLAKE_ACCOUNT``
        Account identifier, e.g. ``xy12345.us-east-1`` or ``orgname-accountname``.

    ``SNOWFLAKE_USER``
        Snowflake username.

    ``SNOWFLAKE_DATABASE``
        Default database for unqualified table references.

    ``SNOWFLAKE_SCHEMA``
        Default schema within the database (e.g. ``PUBLIC``).

    ``SNOWFLAKE_WAREHOUSE``
        Compute warehouse to run queries on.

    Authentication — one of:
    --------------------------------
    ``SNOWFLAKE_PASSWORD``
        Password for username/password authentication.

    ``SNOWFLAKE_PRIVATE_KEY_PATH``
        Path to a PEM-encoded private key file for key-pair authentication.
        ``SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`` may be set if the key is encrypted.

    Optional environment variables
    --------------------------------
    ``SNOWFLAKE_ROLE``
        Snowflake role to assume (default: user's default role).

    Example ``.env`` file::

        SNOWFLAKE_ACCOUNT=xy12345.us-east-1
        SNOWFLAKE_USER=analyst
        SNOWFLAKE_PASSWORD=s3cr3t
        SNOWFLAKE_DATABASE=ANALYTICS
        SNOWFLAKE_SCHEMA=PUBLIC
        SNOWFLAKE_WAREHOUSE=COMPUTE_WH
        SNOWFLAKE_ROLE=ANALYST_ROLE

    Example usage::

        # All config from env vars
        from askmedb.db.snowflake_connector import SnowflakeConnector
        db = SnowflakeConnector()

        # Override specific values (e.g. in tests)
        db = SnowflakeConnector(database="STAGING", schema="RAW")
    """

    def __init__(
        self,
        account: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        warehouse: str | None = None,
        role: str | None = None,
        private_key_path: str | None = None,
        private_key_passphrase: str | None = None,
    ):
        try:
            import snowflake.connector
        except ImportError:
            raise ImportError(
                "snowflake-connector-python is required for SnowflakeConnector. "
                "Install it with: pip install askmedb[snowflake]"
            ) from None

        # Resolve each param: explicit arg → env var → error for required fields
        resolved = {
            "account":   account   or os.environ.get(_ENV_ACCOUNT),
            "user":      user      or os.environ.get(_ENV_USER),
            "database":  database  or os.environ.get(_ENV_DATABASE),
            "schema":    schema    or os.environ.get(_ENV_SCHEMA),
            "warehouse": warehouse or os.environ.get(_ENV_WAREHOUSE),
        }

        missing = [k for k, v in resolved.items() if not v]
        if missing:
            env_names = {
                "account":   _ENV_ACCOUNT,
                "user":      _ENV_USER,
                "database":  _ENV_DATABASE,
                "schema":    _ENV_SCHEMA,
                "warehouse": _ENV_WAREHOUSE,
            }
            missing_vars = ", ".join(env_names[k] for k in missing)
            raise ValueError(
                f"Missing required Snowflake connection parameters: {missing_vars}. "
                f"Set the corresponding environment variables or pass them as arguments."
            )

        resolved_role = role or os.environ.get(_ENV_ROLE)
        if resolved_role:
            resolved["role"] = resolved_role

        # Authentication: key-pair takes priority over password
        resolved_pk_path = private_key_path or os.environ.get(_ENV_PRIVATE_KEY)
        resolved_password = password or os.environ.get(_ENV_PASSWORD)

        if resolved_pk_path:
            resolved_pk_pass = private_key_passphrase or os.environ.get(_ENV_PK_PASS)
            resolved["private_key"] = self._load_private_key(resolved_pk_path, resolved_pk_pass)
        elif resolved_password:
            resolved["password"] = resolved_password
        else:
            raise ValueError(
                f"Snowflake authentication requires either {_ENV_PASSWORD!r} "
                f"(password) or {_ENV_PRIVATE_KEY!r} (key-pair). "
                f"Set one of these environment variables."
            )

        self._conn = snowflake.connector.connect(**resolved)

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query on Snowflake and return results."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return columns, rows
            return [], []
        finally:
            cursor.close()

    def get_dialect(self) -> str:
        return "snowflake"

    def close(self):
        self._conn.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_private_key(path: str, passphrase: str | None = None):
        """Load a PEM private key for key-pair authentication."""
        try:
            from cryptography.hazmat.primitives.serialization import (
                Encoding, PrivateFormat, NoEncryption, load_pem_private_key,
            )
        except ImportError:
            raise ImportError(
                "cryptography is required for Snowflake key-pair auth. "
                "Install it with: pip install askmedb[snowflake]"
            ) from None

        with open(path, "rb") as f:
            pem_data = f.read()

        password_bytes = passphrase.encode() if passphrase else None
        private_key = load_pem_private_key(pem_data, password=password_bytes)
        return private_key.private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
