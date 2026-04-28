# Copyright (c) Saga Inc.
# Distributed under the terms of the GNU Affero General Public License v3.0 License.

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

from mito_ai.db.models import ColumnInfo, TableSchema


# Spark identifiers may legally contain a wide range of characters when backtick-quoted,
# but we still defensively reject backticks to keep injection out of dynamic SQL.
_IDENT_RE = re.compile(r"^[A-Za-z0-9_\-./:+ ]+$")


def _validate_identifier(name: str, label: str) -> Optional[str]:
    if not name or "`" in name or not _IDENT_RE.match(name):
        return f"Invalid {label}: {name!r}"
    return None


def crawl_spark_sql(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    auth: str = "NONE",
) -> Dict[str, Any]:
    """
    Crawl a Spark SQL Thrift Server using the HiveServer2 protocol.

    Spark's information_schema isn't reliably populated, so we use native
    SHOW TABLES IN <db> + DESCRIBE <db>.<table> instead.
    """
    err = _validate_identifier(database, "database name")
    if err:
        return {"schema": None, "error": err}

    try:
        user_q = quote_plus(username) if username else ""
        pwd_q = quote_plus(password) if password else ""
        if user_q and pwd_q:
            userinfo = f"{user_q}:{pwd_q}@"
        elif user_q:
            userinfo = f"{user_q}@"
        else:
            userinfo = ""
        conn_str = f"hive://{userinfo}{host}:{port}/{database}"

        connect_args: Dict[str, Any] = {}
        if auth and auth != "NONE":
            connect_args["auth"] = auth

        engine = (
            create_engine(conn_str, connect_args=connect_args)
            if connect_args
            else create_engine(conn_str)
        )

        schema: TableSchema = {"tables": {}}
        with engine.connect() as connection:
            # SHOW TABLES IN <db> on Spark returns columns: database, tableName, isTemporary
            result = connection.execute(text(f"SHOW TABLES IN `{database}`"))
            tables: List[str] = [row[1] for row in result]

            for table in tables:
                err = _validate_identifier(table, "table name")
                if err:
                    # Skip tables with names we can't safely backtick-quote rather than
                    # failing the whole crawl.
                    continue

                # DESCRIBE returns rows like (col_name, data_type, comment). Once Spark
                # has emitted all schema columns it appends a "# Partition Information"
                # block; we stop at the first row whose col_name is empty or starts with
                # '#' so partition keys aren't double-counted.
                desc = connection.execute(
                    text(f"DESCRIBE `{database}`.`{table}`")
                )
                cols: List[ColumnInfo] = []
                for row in desc:
                    col_name = row[0]
                    data_type = row[1]
                    if not col_name or str(col_name).startswith("#"):
                        break
                    cols.append({"name": col_name, "type": data_type})
                schema["tables"][table] = cols

        return {"schema": schema, "error": None}
    except Exception as e:
        return {"schema": None, "error": str(e)}


def crawl_pyspark(
    master: str,
    app_name: str = "mito-ai-schema",
    database: str = "default",
    hive_metastore_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crawl an embedded SparkSession using the spark.catalog API.

    A new SparkSession is built per crawl, but we deliberately do not call
    spark.stop() because SparkSession is a JVM-level singleton; stopping it
    here would tear down any session a notebook kernel happens to be using.
    """
    try:
        # Imported lazily because pyspark is a 300+ MB optional dependency.
        from pyspark.sql import SparkSession  # type: ignore[import-not-found]
    except ImportError as e:
        return {
            "schema": None,
            "error": f"pyspark is not installed: {e}",
        }

    try:
        builder = SparkSession.builder.appName(app_name).master(master)
        if hive_metastore_uri:
            builder = builder.config(
                "hive.metastore.uris", hive_metastore_uri
            ).enableHiveSupport()
        spark = builder.getOrCreate()

        db = database or "default"
        schema: TableSchema = {"tables": {}}
        for tbl in spark.catalog.listTables(db):
            try:
                cols = spark.catalog.listColumns(tbl.name, db)
            except Exception:
                # Some external tables fail listColumns; record them with an empty
                # column list rather than aborting the whole crawl.
                cols = []
            schema["tables"][tbl.name] = [
                {"name": c.name, "type": c.dataType} for c in cols
            ]

        return {"schema": schema, "error": None}
    except Exception as e:
        return {"schema": None, "error": str(e)}
