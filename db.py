#
# Imports
#

# Standard library
import os
from typing import Any, Optional, Union

# Database
import psycopg2
from psycopg2.extras import RealDictCursor

# Environment variables
from dotenv import load_dotenv
load_dotenv()

# Logging
import logging
logger = logging.getLogger(__name__)


#
# Constants
#

# Database connection parameters
DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}


#
# Helper Functions
#


def get_connection() -> psycopg2.extensions.connection:
    """
    Connect to the PostgreSQL database.

    @returns psycopg2.extensions.connection - Database connection
    """

    logger.debug("Connecting to database")
    return psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)


def execute_query(
    query: str, params: Optional[Union[tuple, dict[str, Any]]] = None
) -> dict[str, Any]:
    """
    Execute SQL query and format results.

    @param query (str): SQL query to execute (use %s placeholders when using params)
    @param params (Optional[Union[tuple, dict]]): Parameters for parameterized query
    @returns dict - Query results with columns, rows, and rowcount
    """

    # Validate query
    if not query:
        raise ValueError("SQL query cannot be empty")

    # Execute the query
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Use parameterized query if params are provided
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # Commit changes
        conn.commit()

        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Fetch all rows
        rows = cursor.fetchall() if cursor.description else []

        # Convert rows to list of values
        result_rows = [[row[column] for column in columns] for row in rows]

        # Get rowcount
        rowcount = cursor.rowcount

        logger.debug("Query executed successfully (rowcount=%d)", rowcount)

        # Clean up
        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        logger.error("Query execution failed: %s", e)
        conn.close()
        raise

    return {"columns": columns, "rows": result_rows, "rowcount": rowcount}
