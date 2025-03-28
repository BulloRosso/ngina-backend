# /services/db_schema_creation.py
import os
import logging
import glob
import psycopg2
from psycopg2 import sql
from typing import List

logger = logging.getLogger(__name__)

class DatabaseSchemaService:
    def __init__(self, db_url):
        """
        Initialize the database schema service.

        Args:
            db_url: PostgreSQL connection string
        """
        self.db_url = db_url

    def create_tables(self, schema_name: str) -> None:
        """
        Create database tables from SQL files if they don't exist yet.
        Only creates tables in the specified schema, not in public.

        Args:
            schema_name: The schema name to create tables in
        """
        # Skip if schema_name is 'public' to ensure we never modify public schema
        if schema_name.lower() == 'public':
            logger.warning("Tables creation in 'public' schema is not allowed. Please specify a custom schema.")
            return

        try:
            # Try to connect with a short timeout
            logger.debug(f"Attempting to connect to database...")

            # For Supabase direct connection, explicitly set connection parameters
            if '://' in self.db_url:
                # Using connection string format
                conn = psycopg2.connect(self.db_url, connect_timeout=10)
            else:
                # Parse connection parameters for explicit connection
                import re
                params = {}
                parts = re.findall(r'([^:=]+)[:=]([^:=]+)', self.db_url)
                for key, value in parts:
                    params[key.strip()] = value.strip()

                conn = psycopg2.connect(
                    user=params.get('user', 'postgres'),
                    password=params.get('password', ''),
                    host=params.get('host', 'localhost'),
                    port=params.get('port', '5432'),
                    dbname=params.get('dbname', 'postgres'),
                    connect_timeout=10
                )

            conn.autocommit = True
            logger.debug("Database connection established successfully")

            try:
                with conn.cursor() as cursor:
                    # First, check if the extensions schema and function exists (no creation)
                    ext_exists = self._check_extensions_exist(cursor)
                    if not ext_exists:
                        logger.error("Required extensions.uuid_generate_v4() function does not exist. Please have a database administrator create it.")
                        return

                    # Check if the schema exists
                    if not self._schema_exists(cursor, schema_name):
                        logger.debug(f"Creating schema '{schema_name}'")
                        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
                        logger.debug(f"Schema '{schema_name}' created successfully")
                    else:
                        logger.debug(f"Schema '{schema_name}' already exists")

                    # Check if the tables already exist - this is just to skip the whole process if all tables are there
                    table_to_check = 'agents'  # Change this if needed to match your specific table name
                    if self._table_exists(cursor, schema_name, table_to_check):
                        logger.debug(f"Table {schema_name}.{table_to_check} already exists. Skipping creation of all tables.")
                        return

                    # Get all SQL files in alphabetical order
                    sql_files = sorted(glob.glob('./services/tables/*.sql'))

                    if not sql_files:
                        logger.warning("No SQL files found in services/tables directory")
                        return

                    # Process each SQL file
                    for sql_file in sql_files:
                        file_name = os.path.basename(sql_file)
                        logger.debug(f"Processing SQL file: {file_name}")

                        # Read file content
                        with open(sql_file, 'r') as f:
                            sql_content = f.read()

                        # Replace 'public.' with the specified schema name
                        sql_content = sql_content.replace('public.', f'{schema_name}.')

                        # Execute SQL statement
                        try:
                            # Split SQL content by semicolons to execute each statement separately
                            statements = sql_content.split(';')
                            for statement in statements:
                                statement = statement.strip()
                                if statement:  # Skip empty statements
                                    # Skip "create table" statements if table already exists
                                    if statement.lower().startswith('create table') and not statement.lower().startswith('create table if not exists'):
                                        # Extract table name from create statement
                                        table_name_match = statement.lower().split('create table')[1].strip().split('(')[0].strip().split('.')
                                        if len(table_name_match) > 1:
                                            extracted_table = table_name_match[1].strip()
                                        else:
                                            extracted_table = table_name_match[0].strip()

                                        # Check if table exists
                                        if self._table_exists(cursor, schema_name, extracted_table):
                                            logger.debug(f"Table {schema_name}.{extracted_table} already exists, skipping creation")
                                            continue

                                    cursor.execute(statement)

                            table_name = self._extract_table_name(file_name)
                            logger.debug(f"Processed SQL file for {schema_name}.{table_name}")
                        except Exception as e:
                            logger.error(f"Error creating table from {file_name}: {str(e)}")
                            raise
            finally:
                # Ensure connection is closed
                conn.close()
                logger.debug("Database connection closed")

        except psycopg2.OperationalError as e:
            logger.error(f"Database connection error: {str(e)}")
            logger.debug("Please check your database connection details and network configuration.")
            raise
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise

    def _check_extensions_exist(self, cursor) -> bool:
        """Check if extensions schema and uuid_generate_v4 function exist without modifying anything"""
        try:
            # Check if extensions schema exists
            cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'extensions')")
            extensions_exists = cursor.fetchone()[0]

            if not extensions_exists:
                logger.warning("Extensions schema does not exist")
                return False

            # Check if the uuid function exists in the extensions schema
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'extensions' AND p.proname = 'uuid_generate_v4')")
            uuid_func_exists = cursor.fetchone()[0]

            if not uuid_func_exists:
                logger.warning("extensions.uuid_generate_v4() function does not exist")
                return False

            logger.debug("extensions.uuid_generate_v4() function exists")
            return True

        except Exception as e:
            logger.error(f"Error checking extensions schema: {str(e)}")
            return False

    def _schema_exists(self, cursor, schema_name: str) -> bool:
        """Check if a schema exists in the database"""
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
            (schema_name,)
        )
        return cursor.fetchone()[0]

    def _table_exists(self, cursor, schema_name: str, table_name: str) -> bool:
        """Check if a table exists in the specific schema"""
        try:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s)",
                (schema_name, table_name)
            )
            exists = cursor.fetchone()[0]
            if exists:
                logger.debug(f"Table {schema_name}.{table_name} exists")
            else:
                logger.debug(f"Table {schema_name}.{table_name} does not exist")
            return exists
        except Exception as e:
            logger.error(f"Error checking if table {schema_name}.{table_name} exists: {str(e)}")
            return False

    def _extract_table_name(self, file_name: str) -> str:
        """Extract table name from file name"""
        # Remove numbering prefix and .sql extension
        # For example, 01_agents.sql becomes agents
        parts = os.path.splitext(file_name)[0].split('_', 1)
        if len(parts) > 1:
            return parts[1]
        return parts[0]


# Singleton instance to be used by the application
_instance = None

def get_db_schema_service(db_url):
    global _instance
    if _instance is None:
        _instance = DatabaseSchemaService(db_url)
    return _instance