from .base import BaseDBConnector
from .sqlite import SQLiteConnector

__all__ = ["BaseDBConnector", "SQLiteConnector"]

# Optional connectors — each requires an extra install extra
try:
    from .sqlalchemy_connector import SQLAlchemyConnector
    __all__.append("SQLAlchemyConnector")
except ImportError:
    pass

try:
    from .pandas_connector import PandasConnector
    __all__.append("PandasConnector")
except ImportError:
    pass

try:
    from .bigquery_connector import BigQueryConnector
    __all__.append("BigQueryConnector")
except ImportError:
    pass

try:
    from .snowflake_connector import SnowflakeConnector
    __all__.append("SnowflakeConnector")
except ImportError:
    pass
