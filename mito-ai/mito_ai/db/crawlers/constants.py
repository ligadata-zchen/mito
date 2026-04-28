# Copyright (c) Saga Inc.
# Distributed under the terms of the GNU Affero General Public License v3.0 License.

from typing import Dict, TypedDict, List


class DatabaseConfig(TypedDict, total=False):
    drivers: List[str]
    tables_query: str
    columns_query: str


SUPPORTED_DATABASES: Dict[str, DatabaseConfig] = {
    "mssql": {
        "drivers": ["pyodbc"],
        "tables_query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'dbo'",
        "columns_query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :table",
    },
    "mysql": {
        "drivers": ["PyMySQL"],
        "tables_query": "SHOW TABLES",
        "columns_query": "SHOW COLUMNS FROM {table}",
    },
    "oracle": {
        "drivers": ["oracledb"],
        "tables_query": "SELECT table_name FROM user_tables",
        "columns_query": "SELECT column_name, data_type FROM user_tab_columns WHERE table_name = :table",
    },
    "postgres": {
        "drivers": ["psycopg2-binary"],
        "tables_query": "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema",
        "columns_query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :table",
    },
    "snowflake": {
        "drivers": ["snowflake-sqlalchemy"],
        # Queries handled in the snowflake.py file.
    },
    "sqlite": {
        "drivers": [],
        "tables_query": "SELECT name FROM sqlite_master WHERE type='table'",
        "columns_query": "SELECT name, type FROM pragma_table_info(:table)",
    },
    "hive": {
        # pyhive provides the SQLAlchemy hive:// dialect; sasl/thrift_sasl are needed
        # for LDAP/Kerberos auth modes.
        "drivers": ["pyhive[hive]", "thrift", "thrift-sasl"],
        "tables_query": "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema",
        "columns_query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :table",
    },
    "trino": {
        # The official Trino python client ships the SQLAlchemy trino:// dialect.
        "drivers": ["trino[sqlalchemy]"],
        "tables_query": "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema",
        "columns_query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :table",
    },
    "presto": {
        # pyhive provides the SQLAlchemy presto:// dialect.
        "drivers": ["pyhive[presto]"],
        "tables_query": "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema",
        "columns_query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :table",
    },
    "bigquery": {
        # sqlalchemy-bigquery provides the bigquery:// dialect; google-cloud-bigquery
        # is required for service-account auth. Queries handled in bigquery.py because
        # INFORMATION_SCHEMA lives under <project>.<dataset>.INFORMATION_SCHEMA and
        # cannot be parameterised in the FROM clause.
        "drivers": ["sqlalchemy-bigquery", "google-cloud-bigquery"],
    },
    "spark_thrift": {
        # Spark SQL exposed over HiveServer2 Thrift protocol. We reuse the pyhive driver,
        # but Spark's information_schema is unreliable across versions, so the crawler
        # uses native SHOW TABLES / DESCRIBE TABLE statements instead.
        "drivers": ["pyhive[hive]", "thrift", "thrift-sasl"],
    },
    "pyspark": {
        # Embedded SparkSession running in-process on the Jupyter host. Heavy install
        # (~300 MB) and requires a JVM. Schema crawl uses the spark.catalog API rather
        # than SQLAlchemy.
        "drivers": ["pyspark"],
    },
}
