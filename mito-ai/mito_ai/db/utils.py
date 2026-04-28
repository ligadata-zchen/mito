# Copyright (c) Saga Inc.
# Distributed under the terms of the GNU Affero General Public License v3.0 License.

import json
import os
from urllib.parse import quote_plus

from mito_ai.db.crawlers import snowflake, base_crawler, bigquery, spark
from mito_ai.db.crawlers.constants import SUPPORTED_DATABASES


def setup_database_dir(
    db_dir_path: str, connections_path: str, schemas_path: str
) -> None:
    """
    Setup the database directory.
    """

    # Ensure the db directory exists
    os.makedirs(db_dir_path, exist_ok=True)

    # Create connections.json if it doesn't exist
    if not os.path.exists(connections_path):
        with open(connections_path, "w") as f:
            json.dump({}, f, indent=4)

    # Create schemas.json if it doesn't exist
    if not os.path.exists(schemas_path):
        with open(schemas_path, "w") as f:
            json.dump({}, f, indent=4)


def save_connection(
    connections_path: str, connection_id: str, connection_details: dict
) -> None:
    """
    Save a connection to the connections.json file.

    Args:
        connections_path (str): The path to the connections.json file.
        connection_id (str): The UUID of the connection to save.
        connection_details (dict): The details of the connection to save.
    """

    with open(connections_path, "r") as f:
        connections = json.load(f)

    # Add the new connection
    connections[connection_id] = connection_details

    # Write back to file
    with open(connections_path, "w") as f:
        json.dump(connections, f, indent=4)


def delete_connection(connections_path: str, connection_id: str) -> None:
    """
    Delete a connection by UUID.
    """

    # Read existing connections
    with open(connections_path, "r") as f:
        connections = json.load(f)

    # Remove the connection
    del connections[connection_id]

    # Write back to file
    with open(connections_path, "w") as f:
        json.dump(connections, f, indent=4)


def delete_schema(schemas_path: str, schema_id: str) -> None:
    """
    Delete a schema by UUID.

    Args:
        schemas_path (str): The path to the schemas.json file.
        schema_id (str): The UUID of the schema to delete.
    """

    with open(schemas_path, "r") as f:
        schemas = json.load(f)

    del schemas[schema_id]

    with open(schemas_path, "w") as f:
        json.dump(schemas, f, indent=4)


def crawl_and_store_schema(
    schemas_path: str,
    connection_id: str,
    connection_details: dict,
) -> dict:
    """
    Crawl and store schema for a given connection.

    Args:
        schemas_path (str): The path to the schemas.json file.
        connection_id (str): The UUID of the connection to crawl.
        username (str): The username for the connection.
        password (str): The password for the connection.
        account (str): The account for the connection.
        warehouse (str): The warehouse for the connection.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and an error message.
    """
    if connection_details["type"] == "snowflake":
        schema = snowflake.crawl_snowflake(
            connection_details["username"],
            connection_details["password"],
            connection_details["account"],
            connection_details["warehouse"],
        )
    elif connection_details["type"] == "postgres":
        conn_str = f"postgresql+psycopg2://{connection_details['username']}:{connection_details['password']}@{connection_details['host']}:{connection_details['port']}/{connection_details['database']}"
        schema = base_crawler.crawl_db(conn_str, "postgres")
    elif connection_details["type"] == "sqlite":
        conn_str = f"sqlite:///{connection_details['database']}"
        schema = base_crawler.crawl_db(conn_str, "sqlite")
    elif connection_details["type"] == "mysql":
        conn_str = f"mysql+pymysql://{connection_details['username']}:{connection_details['password']}@{connection_details['host']}:{connection_details['port']}/{connection_details['database']}"
        schema = base_crawler.crawl_db(conn_str, "mysql")
    elif connection_details["type"] == "mssql":
        odbc_driver_version = connection_details["odbc_driver_version"]
        conn_str = f"mssql+pyodbc://{connection_details['username']}:{connection_details['password']}@{connection_details['host']}:{connection_details['port']}/{connection_details['database']}?driver=ODBC+Driver+{odbc_driver_version}+for+SQL+Server"
        schema = base_crawler.crawl_db(conn_str, "mssql")
    elif connection_details["type"] == "oracle":
        conn_str = f"oracle+oracledb://{connection_details['username']}:{connection_details['password']}@{connection_details['host']}:{connection_details['port']}?service_name={connection_details['service_name']}"
        schema = base_crawler.crawl_db(conn_str, "oracle")
    elif connection_details["type"] == "hive":
        # Hive auth is passed via SQLAlchemy connect_args. Username/password are still
        # encoded in the URL because LDAP auth uses them, but they are URL-quoted to
        # tolerate `@` and `:` in passwords.
        username = quote_plus(connection_details["username"])
        password = quote_plus(connection_details.get("password", ""))
        host = connection_details["host"]
        port = connection_details["port"]
        database = connection_details["database"]
        auth = connection_details.get("auth", "NONE")
        userinfo = f"{username}:{password}@" if password else f"{username}@"
        conn_str = f"hive://{userinfo}{host}:{port}/{database}"
        schema = base_crawler.crawl_db(
            conn_str,
            "hive",
            connect_args={"auth": auth} if auth and auth != "NONE" else None,
            schema_name=database,
        )
    elif connection_details["type"] == "trino":
        username = quote_plus(connection_details["username"])
        password = connection_details.get("password", "")
        host = connection_details["host"]
        port = connection_details["port"]
        catalog = connection_details["catalog"]
        schema_field = connection_details.get("schema", "")
        protocol = connection_details.get("protocol", "https")
        userinfo = f"{username}:{quote_plus(password)}@" if password else f"{username}@"
        path = f"{catalog}/{schema_field}" if schema_field else catalog
        conn_str = f"trino://{userinfo}{host}:{port}/{path}"
        # The trino dialect picks https when a password is supplied; force the
        # user's choice via http_scheme so http-only clusters work too.
        connect_args = {"http_scheme": protocol} if protocol else None
        schema = base_crawler.crawl_db(
            conn_str,
            "trino",
            connect_args=connect_args,
            schema_name=schema_field or "default",
        )
    elif connection_details["type"] == "presto":
        username = quote_plus(connection_details["username"])
        password = connection_details.get("password", "")
        host = connection_details["host"]
        port = connection_details["port"]
        catalog = connection_details["catalog"]
        schema_field = connection_details.get("schema", "")
        userinfo = f"{username}:{quote_plus(password)}@" if password else f"{username}@"
        path = f"{catalog}/{schema_field}" if schema_field else catalog
        conn_str = f"presto://{userinfo}{host}:{port}/{path}"
        schema = base_crawler.crawl_db(
            conn_str,
            "presto",
            schema_name=schema_field or "default",
        )
    elif connection_details["type"] == "bigquery":
        schema = bigquery.crawl_bigquery(
            project_id=connection_details["project_id"],
            dataset=connection_details["dataset"],
            credentials_json=connection_details.get("credentials_json"),
        )
    elif connection_details["type"] == "spark_thrift":
        schema = spark.crawl_spark_sql(
            host=connection_details["host"],
            port=connection_details["port"],
            username=connection_details.get("username", ""),
            password=connection_details.get("password", ""),
            database=connection_details.get("database", "default"),
            auth=connection_details.get("auth", "NONE"),
        )
    elif connection_details["type"] == "pyspark":
        schema = spark.crawl_pyspark(
            master=connection_details["master"],
            app_name=connection_details.get("app_name", "mito-ai-schema"),
            database=connection_details.get("database", "default"),
            hive_metastore_uri=connection_details.get("hive_metastore_uri"),
        )

    if schema["error"]:
        return {
            "success": False,
            "error_message": schema["error"],
            "schema": {},
        }

    # If we successfully crawled the schema, write it to schemas.json
    with open(schemas_path, "r+") as f:
        # Load the existing schemas
        schemas = json.load(f)
        # Remove the error key from the schema and add the crawled schema
        schema.pop("error", None)
        schemas[connection_id] = schema["schema"]
        # Move to the beginning of the file and write the new schema
        f.seek(0)
        json.dump(schemas, f, indent=4)
        f.truncate()
    return {
        "success": True,
        "error_message": "",
        "schema": schema,
    }


def install_db_drivers(db_type: str) -> dict:
    """
    Install required database drivers for the given database type.

    Args:
        db_type (str): The type of database (e.g. 'snowflake', 'postgres')

    Returns:
        dict: A dictionary containing success status and error message if any
    """
    from mito_ai_core.utils.utils import get_installed_packages, install_packages

    installed_packages = get_installed_packages()
    required_packages = SUPPORTED_DATABASES[db_type].get("drivers", [])
    packages_to_install = []

    for package in required_packages:
        if package not in installed_packages:
            packages_to_install.append(package)

    if len(packages_to_install) > 0:
        install_result = install_packages(packages_to_install)
        if not install_result["success"]:
            return {
                "success": False,
                "error": f"Failed to install {db_type} drivers: {install_result['error']}",
            }

    return {"success": True, "error": None}
