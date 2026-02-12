#
# Imports
#

# Standard library
import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

# Database
from dev.db import get_connection

# DAG
from dev.etl.dependency_graph import build_dependency_graph, topological_sort

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#


def find_seed_csv_files(base_path: str, usernames: Optional[list[str]] = None) -> list[str]:
    """Find all seed.csv files, excluding meta/catalog/seed.csv"""
    base = Path(base_path)
    csv_files = []

    # Search in specific usernames or all directories
    search_dirs = [base / u for u in usernames] if usernames else [base]

    for search_dir in search_dirs:
        if search_dir.exists():
            for csv_file in search_dir.rglob("seed.csv"):
                if "meta/catalog/seed.csv" not in str(csv_file):
                    csv_files.append(str(csv_file))

    return csv_files


def find_catalog_csv_files(base_path: str, schemas: Optional[list[str]] = None) -> list[str]:
    """Find all catalog.csv files in specified schemas"""
    if schemas is None:
        schemas = ["meta", "test00000000000000000000"]

    base = Path(base_path)
    csv_files = []

    for schema in schemas:
        schema_dir = base / schema
        if schema_dir.exists():
            for csv_file in schema_dir.rglob("catalog.csv"):
                csv_files.append(str(csv_file))

    return csv_files


def extract_table_name_from_create_sql(create_sql_path: str) -> Optional[str]:
    """Extract table name from create.sql file"""
    try:
        with open(create_sql_path) as f:
            content = f.read()

        # Match CREATE TABLE schema.table or "schema"."table"
        match = re.search(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r'(?:"([^"]+)"\.)?'
            r'(?:"([^"]+)"|([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*))',
            content,
            re.IGNORECASE,
        )

        if match:
            schema = match.group(1)
            quoted_table = match.group(2)
            unquoted_table = match.group(3)
            table_name = quoted_table or unquoted_table

            if schema and table_name:
                return f"{schema}.{table_name}"
            return table_name

        return None
    except Exception:
        return None


def quote_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier if needed"""
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier

    # Quote if starts with digit, has uppercase, or special chars
    needs_quote = (
        identifier[0].isdigit()
        or any(c.isupper() for c in identifier)
        or not identifier.replace("_", "").isalnum()
    )

    return f'"{identifier}"' if needs_quote else identifier


def quote_schema_table(table_name: str) -> str:
    """Quote schema.table identifier"""
    if "." in table_name:
        schema, table = table_name.split(".", 1)
        return f"{quote_identifier(schema)}.{quote_identifier(table)}"
    return quote_identifier(table_name)


def has_serial_column(create_sql_path: str) -> bool:
    """Check if create.sql contains SERIAL columns"""
    try:
        with open(create_sql_path) as f:
            return "SERIAL" in f.read().upper()
    except Exception:
        return False


def reset_serial_sequence(table_name: str, cursor) -> None:
    """Reset SERIAL sequence so nextval returns MAX(ID) + 1"""
    # Parse schema and table (all tables use schema.table format)
    schema, table = table_name.split(".", 1)
    schema = schema.strip('"')
    table = table.strip('"')

    quoted_table = f'"{schema}"."{table}"'
    sequence_name = f'"{schema}"."{table}_ID_seq"'

    # Check if ID column exists
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = 'ID'
        """,
        (schema, table),
    )

    if cursor.fetchone() is None:
        return

    # Get max ID and reset sequence
    # setval(seq, val) sets last_value so nextval returns val + 1
    cursor.execute(f'SELECT COALESCE(MAX("ID"), 0) AS max_id FROM {quoted_table}')
    result = cursor.fetchone()
    max_id = result["max_id"] if result else 0
    seq_val = max(1, max_id)

    cursor.execute(f"SELECT setval('{sequence_name}', {seq_val})")
    logger.info(f"Reset sequence {sequence_name} to {seq_val}")


def seed_catalog_files(tables_dir: Path) -> int:
    """Seed meta.catalog from catalog.csv files"""
    catalog_files = find_catalog_csv_files(str(tables_dir))
    if not catalog_files:
        return 0

    # Sort for deterministic insertion order
    catalog_files.sort()

    # Clear meta.catalog first (table always exists in normal operation)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meta.catalog")
    conn.commit()
    cursor.close()
    conn.close()

    catalogs_seeded = 0

    for catalog_file in catalog_files:
        with open(catalog_file, newline="") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            continue

        conn = get_connection()
        cursor = conn.cursor()

        # Insert each row
        insert_query = """
            INSERT INTO meta.catalog
            ("Table", "Column", "Order", "Type", "Nullable?", "Primary Key?",
             "Foreign Key", "Description", "Sample Values")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for row in rows:
            # Parse booleans
            nullable_str = row.get("Nullable?", "").strip().upper()
            nullable = (
                True if nullable_str == "TRUE" else (False if nullable_str == "FALSE" else None)
            )

            pk_str = row.get("Primary Key?", "").strip().upper()
            pk = True if pk_str == "TRUE" else (False if pk_str == "FALSE" else None)

            # Parse other fields
            order_val = int(row.get("Order", 0))
            column_val = row.get("Column", "").strip()
            column_val = None if column_val.upper() == "NULL" or column_val == "" else column_val
            fk_val = row.get("Foreign Key", "").strip() or None

            cursor.execute(
                insert_query,
                (
                    row.get("Table"),
                    column_val,
                    order_val,
                    row.get("Type"),
                    nullable,
                    pk,
                    fk_val,
                    row.get("Description") or None,
                    row.get("Sample Values") or None,
                ),
            )

        conn.commit()
        cursor.close()
        conn.close()
        catalogs_seeded += 1

    return catalogs_seeded


#
# Handler Functions
#


def seed_table(usernames: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Seed tables from CSV files

    @param usernames (Optional[list[str]]): Filter by specific usernames/schemas
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("seed_table called")

    # Get tables directory
    from dev.paths import TABLES_DIR
    tables_dir = TABLES_DIR

    # Find seed.csv files
    csv_files = find_seed_csv_files(str(tables_dir), usernames if usernames else None)

    # Build table_name -> csv_file mapping and collect create.sql paths
    csv_by_table: dict[str, str] = {}
    create_sql_paths: list[str] = []
    for csv_file in csv_files:
        csv_path = Path(csv_file)
        create_sql_path = csv_path.parent / "create.sql"
        if not create_sql_path.exists():
            continue

        table_name = extract_table_name_from_create_sql(str(create_sql_path))
        if table_name:
            csv_by_table[table_name] = csv_file
            create_sql_paths.append(str(create_sql_path))

    # Build dependency graph and get topological order
    graph, _ = build_dependency_graph(create_sql_paths, extract_table_name_from_create_sql)
    ordered = topological_sort(graph)

    # Tables in the graph that have csv files, plus any csv tables not in the graph
    ordered_tables = [name for name in ordered if name in csv_by_table]
    unordered_tables = [name for name in csv_by_table if name not in set(ordered_tables)]

    # Track progress
    failed_tables: dict[str, str] = {}
    total_seeded = 0

    # Single pass: seed each table in dependency order
    for table_name in ordered_tables + unordered_tables:
        csv_file = csv_by_table[table_name]
        create_sql_path = str(Path(csv_file).parent / "create.sql")

        try:
            # Import CSV using COPY
            quoted_table = quote_schema_table(table_name)
            conn = get_connection()
            cursor = conn.cursor()

            # Truncate table first to ensure clean seed
            cursor.execute(f"TRUNCATE {quoted_table} CASCADE")
            conn.commit()

            with open(csv_file) as f:
                next(f)  # Skip header
                cursor.copy_expert(
                    f"COPY {quoted_table} FROM STDIN WITH (FORMAT csv, HEADER false, NULL '')",
                    f,
                )

            conn.commit()
            cursor.close()
            conn.close()

            # Reset SERIAL sequence if needed
            if has_serial_column(create_sql_path):
                reset_conn = get_connection()
                reset_cursor = reset_conn.cursor()
                reset_serial_sequence(table_name, reset_cursor)
                reset_conn.commit()
                reset_cursor.close()
                reset_conn.close()

            total_seeded += 1
            failed_tables.pop(table_name, None)

        except Exception as e:
            failed_tables[table_name] = f"{table_name}: {str(e)}"
            logger.warning(f"Failed to seed {table_name}: {e}")

    # Seed catalog files
    catalogs_seeded = seed_catalog_files(tables_dir)

    logger.info(f"seed_table completed: {total_seeded} tables, {catalogs_seeded} catalogs")

    response: dict[str, Any] = {
        "status": "success",
        "message": f"Seeded {total_seeded} tables, {catalogs_seeded} catalogs",
        "tables_seeded": total_seeded,
        "catalogs_seeded": catalogs_seeded,
    }

    if failed_tables:
        response["failed_tables"] = len(failed_tables)

    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed database tables")
    parser.add_argument("--usernames", nargs="*", help="Filter by usernames/schemas")
    args = parser.parse_args()
    result = seed_table(usernames=args.usernames)
    print(json.dumps(result, indent=2))
