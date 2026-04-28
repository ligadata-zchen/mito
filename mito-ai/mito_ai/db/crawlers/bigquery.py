# Copyright (c) Saga Inc.
# Distributed under the terms of the GNU Affero General Public License v3.0 License.

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text

from mito_ai.db.models import ColumnInfo, TableSchema


def crawl_bigquery(
    project_id: str,
    dataset: str,
    credentials_json: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crawl a BigQuery dataset and return its tables and column definitions.

    Auth modes:
      - credentials_json: a service-account JSON blob (string). Optional —
        when omitted, sqlalchemy-bigquery falls back to Application Default
        Credentials (ADC) on the Jupyter host (gcloud login or GOOGLE_APPLICATION_CREDENTIALS).

    INFORMATION_SCHEMA on BigQuery lives at <project>.<dataset>.INFORMATION_SCHEMA.*,
    so the dataset must be baked into the FROM clause; it cannot be a bound param.
    """
    try:
        connect_args: Dict[str, Any] = {}
        if credentials_json:
            try:
                connect_args["credentials_info"] = json.loads(credentials_json)
            except json.JSONDecodeError as e:
                return {
                    "schema": None,
                    "error": f"Invalid service-account JSON: {e}",
                }

        engine = create_engine(
            f"bigquery://{project_id}",
            connect_args=connect_args or None,
        )

        # Backtick-quote the project + dataset to allow hyphens (common in GCP project ids).
        # We validate inputs to forbid backticks so a malicious id can't break out of the
        # quoting and inject SQL.
        if "`" in project_id or "`" in dataset:
            return {
                "schema": None,
                "error": "Project id and dataset must not contain backticks.",
            }

        tables_query = text(
            f"SELECT table_name FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.TABLES`"
        )
        columns_query = text(
            f"SELECT column_name, data_type FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.COLUMNS` "
            "WHERE table_name = :table"
        )

        schema: TableSchema = {"tables": {}}

        with engine.connect() as connection:
            result = connection.execute(tables_query)
            tables: List[str] = [row[0] for row in result]

            for table in tables:
                cols_result = connection.execute(columns_query, {"table": table})
                column_info: List[ColumnInfo] = [
                    {"name": row[0], "type": row[1]} for row in cols_result
                ]
                schema["tables"][table] = column_info

        return {"schema": schema, "error": None}
    except Exception as e:
        return {"schema": None, "error": str(e)}
