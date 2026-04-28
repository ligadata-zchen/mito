/*
 * Copyright (c) Saga Inc.
 * Distributed under the terms of the GNU Affero General Public License v3.0 License.
 */

export interface DBConnection {
    type: string;
    [key: string]: string | number | undefined;
}

export interface DBConnections {
    [key: string]: DBConnection;  // key is now UUID
}

export interface DatabaseField {
    name: string;
    type: 'text' | 'password' | 'number' | 'select' | 'textarea';
    label: string;
    placeholder?: string;
    helpText?: string;
    required: boolean;
    options?: Array<{ value: string; label: string }>;
}

export interface DatabaseConfig {
    type: string;
    displayName: string;
    alertText?: string;  // Optional HTML content for alerts/notifications
    fields: DatabaseField[];
}

const ALIAS_PLACEHOLDER = 'Enter a nickname for this database';

export const databaseConfigs: Record<string, DatabaseConfig> = {
    mssql: {
        type: 'mssql',
        displayName: 'Microsoft SQL Server',
        alertText: 'Microsoft SQL Server requires an additional driver. If you\'ve already installed it, you can safely ignore this message. For more info, consult the <a href="https://docs.trymito.io/mito-ai/database-connectors/microsoft-sql-server" target="_blank">Mito docs</a>.',
        fields: [
            {
                name: 'alias',
                type: 'text',
                label: 'Alias',
                placeholder: ALIAS_PLACEHOLDER,
                required: true
            },
            {
                name: 'username',
                type: 'text',
                label: 'Username',
                placeholder: 'john.doe',
                required: true
            },
            {
                name: 'password',
                type: 'password',
                label: 'Password',
                placeholder: 'Enter your password',
                required: true
            },
            {
                name: 'host',
                type: 'text',
                label: 'Host',
                placeholder: 'localhost',
                required: true
            },
            {
                name: 'port',
                type: 'number',
                label: 'Port',
                placeholder: '1433',
                required: true
            },
            {
                name: 'database',
                type: 'text',
                label: 'Database',
                placeholder: 'mydb',
                required: true
            },
            {
                name: 'odbc_driver_version',
                type: 'text',
                label: 'ODBC Driver Version',
                placeholder: '18',
                required: true
            }
        ]
    },
    mysql: {
        type: 'mysql',
        displayName: 'MySQL',
        fields: [
            {
                name: 'alias',
                type: 'text',
                label: 'Alias',
                placeholder: ALIAS_PLACEHOLDER,
                required: true
            },
            {
                name: 'username',
                type: 'text',
                label: 'Username',
                placeholder: 'john.doe',
                required: true
            },
            {
                name: 'password',
                type: 'password',
                label: 'Password',
                placeholder: 'Enter your password',
                required: true
            },
            {
                name: 'host',
                type: 'text',
                label: 'Host',
                placeholder: 'localhost',
                required: true
            },
            {
                name: 'port',
                type: 'number',
                label: 'Port',
                placeholder: '3306',
                required: true
            },
            {
                name: 'database',
                type: 'text',
                label: 'Database',
                placeholder: 'mydb',
                required: true
            }
        ]
    },
    oracle: {
        type: 'oracle',
        displayName: 'Oracle',
        fields: [
            {
                name: 'alias',
                type: 'text',
                label: 'Alias',
                placeholder: ALIAS_PLACEHOLDER,
                required: true
            },
            {
                name: 'username',
                type: 'text',
                label: 'Username',
                placeholder: 'john.doe',
                required: true
            },
            {
                name: 'password',
                type: 'password',
                label: 'Password',
                placeholder: 'Enter your password',
                required: true
            },
            {
                name: 'host',
                type: 'text',
                label: 'Host',
                placeholder: 'localhost',
                required: true
            },
            {
                name: 'port',
                type: 'number',
                label: 'Port',
                placeholder: '1521',
                required: true
            },
            {
                name: 'service_name',
                type: 'text',
                label: 'Service Name',
                placeholder: 'xe',
                required: true
            }
        ]
    },
    postgres: {
        type: 'postgres',
        displayName: 'PostgreSQL',
        fields: [
            {
                name: 'alias',
                type: 'text',
                label: 'Alias',
                placeholder: ALIAS_PLACEHOLDER,
                required: true
            },
            {
                name: 'username',
                type: 'text',
                label: 'Username',
                placeholder: 'john.doe',
                required: true
            },
            {
                name: 'password',
                type: 'password',
                label: 'Password',
                placeholder: 'Enter your password',
                required: true
            },
            {
                name: 'host',
                type: 'text',
                label: 'Host',
                placeholder: 'localhost',
                required: true
            },
            {
                name: 'port',
                type: 'number',
                label: 'Port',
                placeholder: '5432',
                required: true
            },
            {
                name: 'database',
                type: 'text',
                label: 'Database',
                placeholder: 'mydb',
                required: true
            }
        ]
    },
    snowflake: {
        type: 'snowflake',
        displayName: 'Snowflake',
        fields: [
            {
                name: 'alias',
                type: 'text',
                label: 'Alias',
                placeholder: ALIAS_PLACEHOLDER,
                required: true
            },
            {
                name: 'username',
                type: 'text',
                label: 'Username',
                placeholder: 'john.doe',
                required: true
            },
            {
                name: 'password',
                type: 'password',
                label: 'Password',
                placeholder: 'Enter your password',
                required: true
            },
            {
                name: 'account',
                type: 'text',
                label: 'Account',
                placeholder: 'tudbfdr-ab12345',
                required: true
            },
            {
                name: 'warehouse',
                type: 'text',
                label: 'Warehouse',
                placeholder: 'COMPUTE_WH',
                required: true
            }
        ]
    },
    sqlite: {
        type: 'sqlite',
        displayName: 'SQLite',
        fields: [
            {
                name: 'alias',
                type: 'text',
                label: 'Alias',
                placeholder: ALIAS_PLACEHOLDER,
                required: true
            },
            {
                name: 'database',
                type: 'text',
                label: 'Path to database',
                placeholder: '/Users/jake/db.sqlite3',
                required: true
            }
        ]
    },
    hive: {
        type: 'hive',
        displayName: 'Apache Hive',
        alertText: 'Hive uses Thrift; LDAP/Kerberos auth requires the system <code>libsasl2</code> package on the Jupyter host.',
        fields: [
            { name: 'alias', type: 'text', label: 'Alias', placeholder: ALIAS_PLACEHOLDER, required: true },
            { name: 'username', type: 'text', label: 'Username', placeholder: 'john.doe', required: true },
            { name: 'password', type: 'password', label: 'Password', placeholder: 'Required for LDAP auth', required: false },
            { name: 'host', type: 'text', label: 'Host', placeholder: 'hive-server.example.com', required: true },
            { name: 'port', type: 'number', label: 'Port', placeholder: '10000', required: true },
            { name: 'database', type: 'text', label: 'Database', placeholder: 'default', required: true },
            {
                name: 'auth',
                type: 'select',
                label: 'Auth Mode',
                required: true,
                options: [
                    { value: 'NONE', label: 'None' },
                    { value: 'LDAP', label: 'LDAP' },
                    { value: 'KERBEROS', label: 'Kerberos' }
                ]
            }
        ]
    },
    trino: {
        type: 'trino',
        displayName: 'Trino',
        fields: [
            { name: 'alias', type: 'text', label: 'Alias', placeholder: ALIAS_PLACEHOLDER, required: true },
            { name: 'username', type: 'text', label: 'Username', placeholder: 'john.doe', required: true },
            { name: 'password', type: 'password', label: 'Password', placeholder: 'Optional (omit for kerberos / cluster-side auth)', required: false },
            { name: 'host', type: 'text', label: 'Host', placeholder: 'trino.example.com', required: true },
            { name: 'port', type: 'number', label: 'Port', placeholder: '443', required: true },
            { name: 'catalog', type: 'text', label: 'Catalog', placeholder: 'hive', required: true },
            { name: 'schema', type: 'text', label: 'Schema', placeholder: 'default', required: false },
            {
                name: 'protocol',
                type: 'select',
                label: 'Protocol',
                required: true,
                options: [
                    { value: 'https', label: 'HTTPS' },
                    { value: 'http', label: 'HTTP' }
                ]
            }
        ]
    },
    presto: {
        type: 'presto',
        displayName: 'Presto',
        fields: [
            { name: 'alias', type: 'text', label: 'Alias', placeholder: ALIAS_PLACEHOLDER, required: true },
            { name: 'username', type: 'text', label: 'Username', placeholder: 'john.doe', required: true },
            { name: 'password', type: 'password', label: 'Password', placeholder: 'Optional', required: false },
            { name: 'host', type: 'text', label: 'Host', placeholder: 'presto.example.com', required: true },
            { name: 'port', type: 'number', label: 'Port', placeholder: '8080', required: true },
            { name: 'catalog', type: 'text', label: 'Catalog', placeholder: 'hive', required: true },
            { name: 'schema', type: 'text', label: 'Schema', placeholder: 'default', required: false }
        ]
    },
    bigquery: {
        type: 'bigquery',
        displayName: 'Google BigQuery',
        alertText: 'Paste a service-account JSON key for auth. Leave blank to use Application Default Credentials (ADC) on the Jupyter host.',
        fields: [
            { name: 'alias', type: 'text', label: 'Alias', placeholder: ALIAS_PLACEHOLDER, required: true },
            { name: 'project_id', type: 'text', label: 'Project ID', placeholder: 'my-gcp-project', required: true },
            { name: 'dataset', type: 'text', label: 'Dataset', placeholder: 'analytics', required: true },
            {
                name: 'credentials_json',
                type: 'textarea',
                label: 'Service Account JSON',
                placeholder: '{ "type": "service_account", "project_id": "...", ... }',
                helpText: 'Optional. Paste the entire JSON key contents.',
                required: false
            }
        ]
    },
    spark_thrift: {
        type: 'spark_thrift',
        displayName: 'Spark SQL (Thrift Server)',
        alertText: 'Connects to a Spark Thrift Server using the HiveServer2 protocol. LDAP/Kerberos auth needs the system <code>libsasl2</code> package on the Jupyter host.',
        fields: [
            { name: 'alias', type: 'text', label: 'Alias', placeholder: ALIAS_PLACEHOLDER, required: true },
            { name: 'host', type: 'text', label: 'Host', placeholder: 'spark-thrift.example.com', required: true },
            { name: 'port', type: 'number', label: 'Port', placeholder: '10000', required: true },
            { name: 'database', type: 'text', label: 'Database', placeholder: 'default', required: true },
            { name: 'username', type: 'text', label: 'Username', placeholder: 'Required for LDAP', required: false },
            { name: 'password', type: 'password', label: 'Password', placeholder: 'Required for LDAP', required: false },
            {
                name: 'auth',
                type: 'select',
                label: 'Auth Mode',
                required: true,
                options: [
                    { value: 'NONE', label: 'None' },
                    { value: 'LDAP', label: 'LDAP' },
                    { value: 'KERBEROS', label: 'Kerberos' }
                ]
            }
        ]
    },
    pyspark: {
        type: 'pyspark',
        displayName: 'PySpark (embedded SparkSession)',
        alertText: 'Runs an in-process SparkSession on the Jupyter host. Requires Java; the <code>pyspark</code> wheel is large (~300 MB). For a Hive metastore-backed cluster, set the metastore URI below.',
        fields: [
            { name: 'alias', type: 'text', label: 'Alias', placeholder: ALIAS_PLACEHOLDER, required: true },
            {
                name: 'master',
                type: 'text',
                label: 'Spark Master URL',
                placeholder: 'local[*] | spark://host:7077 | yarn | k8s://...',
                helpText: 'Use local[*] to run against a local in-process cluster.',
                required: true
            },
            { name: 'app_name', type: 'text', label: 'App Name', placeholder: 'mito-ai-schema', required: false },
            { name: 'database', type: 'text', label: 'Database', placeholder: 'default', required: false },
            {
                name: 'hive_metastore_uri',
                type: 'text',
                label: 'Hive Metastore URI',
                placeholder: 'thrift://metastore.example.com:9083',
                helpText: 'Optional. When set, Hive support is enabled and tables are read from the shared metastore.',
                required: false
            }
        ]
    }
};
