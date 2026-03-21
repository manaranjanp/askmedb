"""Google BigQuery connector for AskMeDB."""

import os

from .base import BaseDBConnector


# Environment variables read by this connector
_ENV_PROJECT_ID      = "BIGQUERY_PROJECT_ID"
_ENV_CREDENTIALS     = "GOOGLE_APPLICATION_CREDENTIALS"   # path to service-account JSON
_ENV_LOCATION        = "BIGQUERY_LOCATION"
_ENV_DEFAULT_DATASET = "BIGQUERY_DATASET"


class BigQueryConnector(BaseDBConnector):
    """Execute SQL queries against Google BigQuery.

    All connection parameters are read from **environment variables** by default.
    Constructor arguments are optional overrides — useful for testing or when
    managing multiple connections in the same process.

    Required environment variables
    --------------------------------
    ``BIGQUERY_PROJECT_ID``
        GCP project that will be billed for queries.

    ``GOOGLE_APPLICATION_CREDENTIALS``
        Path to a service-account JSON key file.  When this variable is set,
        google-auth loads the credentials automatically — no code changes needed.
        Alternatively, run ``gcloud auth application-default login`` to use
        Application Default Credentials (ADC) without a key file.

    Optional environment variables
    --------------------------------
    ``BIGQUERY_LOCATION``
        BigQuery processing location / region (default: ``"US"``).

    ``BIGQUERY_DATASET``
        Default dataset ID.  When set, SQL queries can reference tables with
        just ``table_name`` instead of ``project.dataset.table_name``.

    Example ``.env`` file::

        BIGQUERY_PROJECT_ID=my-gcp-project
        GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
        BIGQUERY_LOCATION=US
        BIGQUERY_DATASET=analytics

    Example usage::

        # All config from env vars
        from askmedb.db.bigquery_connector import BigQueryConnector
        db = BigQueryConnector()

        # Override specific values (e.g. in tests)
        db = BigQueryConnector(project_id="test-project", location="EU")
    """

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        default_dataset: str | None = None,
    ):
        try:
            from google.cloud import bigquery
        except ImportError:
            raise ImportError(
                "google-cloud-bigquery is required for BigQueryConnector. "
                "Install it with: pip install askmedb[bigquery]"
            ) from None

        resolved_project = project_id or os.environ.get(_ENV_PROJECT_ID)
        if not resolved_project:
            raise ValueError(
                f"BigQuery project ID is required. "
                f"Set the {_ENV_PROJECT_ID!r} environment variable or pass project_id=."
            )

        resolved_location = location or os.environ.get(_ENV_LOCATION, "US")
        resolved_dataset  = default_dataset or os.environ.get(_ENV_DEFAULT_DATASET)

        # google-auth automatically reads GOOGLE_APPLICATION_CREDENTIALS when
        # present, so we do not need to handle it explicitly — just document it.
        self._client = bigquery.Client(
            project=resolved_project,
            location=resolved_location,
        )

        job_config = bigquery.QueryJobConfig()
        if resolved_dataset:
            job_config.default_dataset = f"{resolved_project}.{resolved_dataset}"
        self._job_config = job_config

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query on BigQuery and return results."""
        query_job = self._client.query(sql, job_config=self._job_config)
        result = query_job.result()   # blocks until the job completes
        columns = [field.name for field in result.schema]
        rows = [tuple(row) for row in result]
        return columns, rows

    def get_dialect(self) -> str:
        return "bigquery"

    def close(self):
        self._client.close()
