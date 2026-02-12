#
# Imports
#

# Standard library
import argparse
import json
import logging
from pathlib import Path
from typing import Any, Optional

# Database
from dev.db import execute_query

# DAG
from dev.etl.dependency_graph import build_dependency_graph, topological_sort
from dev.etl.seed_tables import extract_table_name_from_create_sql

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#


def find_create_sql_files(base_path: str, usernames: Optional[list[str]] = None) -> list[str]:
    """Find all create.sql files in the tables directory"""
    sql_files = []
    base = Path(base_path)

    # Search in specific usernames or all directories
    search_dirs = [base / u for u in usernames] if usernames else [base]

    for search_dir in search_dirs:
        if search_dir.exists():
            for sql_file in search_dir.rglob("create.sql"):
                sql_files.append(str(sql_file))

    return sql_files


#
# Handler Functions
#


def create_table(usernames: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Create database tables from SQL files

    @param usernames (Optional[list[str]]): Filter by specific usernames/schemas
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("create_table called")

    # Get tables directory
    from dev.paths import TABLES_DIR
    tables_dir = TABLES_DIR

    # Find all create.sql files
    sql_files = find_create_sql_files(str(tables_dir), usernames if usernames else None)

    # Build dependency graph and get topological order
    graph, file_map = build_dependency_graph(sql_files, extract_table_name_from_create_sql)
    ordered = topological_sort(graph)

    # Collect files not in the graph (no extractable table name)
    ordered_files = [file_map[name] for name in ordered if name in file_map]
    unordered_files = [f for f in sql_files if f not in set(ordered_files)]

    # Track progress
    failed_tables: dict[str, str] = {}
    total_created = 0

    # Single pass: create each table in dependency order, then unordered files
    for sql_file in ordered_files + unordered_files:
        try:
            with open(sql_file) as f:
                sql_content = f.read()

            execute_query(sql_content)
            total_created += 1

        except Exception as e:
            failed_tables[sql_file] = str(e)
            logger.warning(f"Failed to create table from {sql_file}: {e}")

    logger.info(f"create_table completed: {total_created} tables created")

    response: dict[str, Any] = {
        "status": "success",
        "message": f"Created {total_created} tables",
        "tables_created": total_created,
    }

    if failed_tables:
        response["failed_tables"] = len(failed_tables)

    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create database tables")
    parser.add_argument("--usernames", nargs="*", help="Filter by usernames/schemas")
    args = parser.parse_args()
    result = create_table(usernames=args.usernames)
    print(json.dumps(result, indent=2))
