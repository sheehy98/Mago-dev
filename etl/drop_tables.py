#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any, Optional

# Database
from dev.db import execute_query

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#


def quote_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier if needed"""
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier

    needs_quote = (
        identifier[0].isdigit()
        or any(c.isupper() for c in identifier)
        or not identifier.replace("_", "").isalnum()
    )

    return f'"{identifier}"' if needs_quote else identifier


#
# Handler Functions
#


def drop_table(schemas: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Drop database schemas

    @param schemas (Optional[list[str]]): Schemas to drop (derives from data/tables if None)
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("drop_table called")

    # If no schemas specified, drop all non-system schemas from the database
    if not schemas:
        result = execute_query(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname NOT LIKE 'pg_%%' AND nspname NOT IN ('information_schema', 'public');"
        )
        schemas = [row[0] for row in result["rows"]]

    # Drop each schema
    for schema in schemas:
        quoted_schema = quote_identifier(schema)
        execute_query(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE;")

    logger.info(f"drop_table completed: {len(schemas)} schemas dropped")
    return {
        "status": "success",
        "message": f"Dropped {len(schemas)} schema(s)",
        "schemas_dropped": len(schemas),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop database schemas")
    parser.add_argument("-s", "--staging", action="store_true", help="Use staging environment")
    parser.add_argument("--schemas", nargs="*", help="Schemas to drop")
    args = parser.parse_args()
    result = drop_table(schemas=args.schemas)
    print(json.dumps(result, indent=2))
