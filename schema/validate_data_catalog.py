#
# Imports
#

# Standard library
import argparse
import csv
import json
import logging
from typing import Any

# Database functions
from dev.db import execute_query

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#


def get_database_schema(schema: str) -> dict[str, list[dict[str, Any]]]:
    """
    Get all tables and columns from database for a given schema including primary keys

    @param schema (str): Schema name (e.g., 'meta', 'test')
    @returns Dict[str, List[Dict[str, Any]]] - Dictionary mapping table name to list of columns
    """

    # Query all tables in the schema
    tables_query = f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = '{schema}'
        ORDER BY table_name;
    """
    tables_result = execute_query(tables_query)

    schema_structure = {}

    for table_row in tables_result["rows"]:
        table_name = table_row[0]
        full_table_name = f"{schema}.{table_name}"

        # Query primary key columns for this table
        pk_query = f"""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = '{schema}'
            AND tc.table_name = '{table_name}'
            AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position;
        """
        pk_result = execute_query(pk_query)
        pk_columns = {row[0] for row in pk_result["rows"]}

        # Query foreign key constraints for this table
        # For composite FKs, we need to match columns by position
        fk_query = f"""
            SELECT
                kcu.column_name,
                kcu.ordinal_position,
                kcu_ref.table_schema || '.' || kcu_ref.table_name || '.' || kcu_ref.column_name AS foreign_key
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.table_schema = rc.constraint_schema
            JOIN information_schema.key_column_usage kcu_ref
                ON rc.unique_constraint_name = kcu_ref.constraint_name
                AND rc.unique_constraint_schema = kcu_ref.table_schema
                AND kcu.ordinal_position = kcu_ref.ordinal_position
            WHERE tc.table_schema = '{schema}'
            AND tc.table_name = '{table_name}'
            AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.constraint_name, kcu.ordinal_position;
        """
        fk_result = execute_query(fk_query)
        fk_map = {row[0]: row[2] for row in fk_result["rows"]}

        # Query columns for this table
        columns_query = f"""
            SELECT
                column_name,
                ordinal_position,
                data_type,
                udt_name,
                is_nullable,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns
            WHERE table_schema = '{schema}'
            AND table_name = '{table_name}'
            ORDER BY ordinal_position;
        """
        columns_result = execute_query(columns_query)

        columns = []
        for col_row in columns_result["rows"]:
            col_name = col_row[0]
            ordinal_pos = col_row[1]
            data_type = col_row[2]
            is_nullable = col_row[4] == "YES"
            num_precision = col_row[6]
            num_scale = col_row[7]

            # Format type (NUMERIC needs precision/scale)
            pg_type = data_type.upper()
            if pg_type == "NUMERIC" and num_precision and num_scale:
                pg_type = f"NUMERIC({num_precision},{num_scale})"

            columns.append(
                {
                    "name": col_name,
                    "order": ordinal_pos,
                    "type": pg_type,
                    "nullable": is_nullable,
                    "primary_key": col_name in pk_columns,
                    "foreign_key": fk_map.get(col_name),
                }
            )

        schema_structure[full_table_name] = columns

    return schema_structure


def get_catalog_schema() -> dict[str, list[dict[str, Any]]]:
    """
    Get all documented tables and columns from catalog.csv files

    @returns Dict[str, List[Dict[str, Any]]] - Dictionary mapping table name to list of columns
    """

    # Get the tables directory from centralized paths
    from dev.paths import TABLES_DIR
    data_dir = TABLES_DIR

    catalog_structure = {}

    # Find all catalog.csv files recursively
    catalog_files = list(data_dir.rglob("catalog.csv"))

    logger.info(f"Found {len(catalog_files)} catalog.csv files")

    for catalog_file in catalog_files:
        with open(catalog_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Skip table-level metadata rows (Order = 0 or NULL)
                order_str = row.get("Order", "").strip()
                if not order_str or order_str == "0" or order_str == "NULL":
                    continue

                order = int(order_str)
                table_name = row.get("Table", "").strip()
                col_name = row.get("Column", "").strip()

                col_type = row.get("Type", "").strip()
                nullable_str = row.get("Nullable?", "").strip()
                primary_key_str = row.get("Primary Key?", "").strip()
                foreign_key = row.get("Foreign Key", "").strip() or None

                # Parse nullable (can be TRUE, FALSE, or empty)
                nullable = None
                if nullable_str.upper() == "TRUE":
                    nullable = True
                elif nullable_str.upper() == "FALSE":
                    nullable = False

                # Parse primary key (can be TRUE, FALSE, or empty)
                primary_key = None
                if primary_key_str.upper() == "TRUE":
                    primary_key = True
                elif primary_key_str.upper() == "FALSE":
                    primary_key = False

                if table_name not in catalog_structure:
                    catalog_structure[table_name] = []

                catalog_structure[table_name].append(
                    {
                        "name": col_name,
                        "order": order,
                        "type": col_type,
                        "nullable": nullable,
                        "primary_key": primary_key,
                        "foreign_key": foreign_key,
                    }
                )

    logger.info(f"Loaded {len(catalog_structure)} tables from catalog files")
    return catalog_structure


#
# Handler Functions
#


def validate_data_catalog() -> dict[str, Any]:
    """
    Validate data catalog against database schema

    Compares actual database schema with catalog documentation and reports:
    - Missing columns (in DB but not in catalog)
    - Extra columns (in catalog but not in DB)
    - Order mismatches
    - Type mismatches
    - Nullability mismatches
    - Extra tables (in catalog but not in DB)
    - Missing tables (in DB but not in catalog for meta/test schemas)

    @returns Dict[str, Any] - Response with validation results
    """

    logger.info("validate_data_catalog called")

    # Get actual database schema for meta and test
    meta_db_schema = get_database_schema("meta")
    test_db_schema = get_database_schema("test00000000000000000000")
    db_schema = {**meta_db_schema, **test_db_schema}

    # Get catalog documentation
    catalog_schema = get_catalog_schema()

    # Track validation results
    issues = []

    # Check for missing tables (in DB but not in catalog)
    db_tables = set(db_schema.keys())
    catalog_tables = set(catalog_schema.keys())

    missing_tables = db_tables - catalog_tables
    for table in sorted(missing_tables):
        issues.append(
            {
                "type": "missing_table",
                "table": table,
                "message": f"Table '{table}' exists in database but not documented in catalog",
            }
        )

    # Check for extra tables (in catalog but not in DB)
    extra_tables = catalog_tables - db_tables
    for table in sorted(extra_tables):
        issues.append(
            {
                "type": "extra_table",
                "table": table,
                "message": f"Table '{table}' documented in catalog but does not exist in database",
            }
        )

    # Check tables that exist in both
    common_tables = db_tables & catalog_tables

    for table in sorted(common_tables):
        db_columns = db_schema[table]
        catalog_columns = catalog_schema[table]

        # Create maps for easy lookup
        db_col_map = {col["name"]: col for col in db_columns}
        catalog_col_map = {col["name"]: col for col in catalog_columns}

        db_col_names = set(db_col_map.keys())
        catalog_col_names = set(catalog_col_map.keys())

        # Check for missing columns (in DB but not in catalog)
        missing_columns = db_col_names - catalog_col_names
        for col_name in sorted(missing_columns):
            issues.append(
                {
                    "type": "missing_column",
                    "table": table,
                    "column": col_name,
                    "message": f"Column '{col_name}' exists in database but not documented in catalog",
                }
            )

        # Check for extra columns (in catalog but not in DB)
        extra_columns = catalog_col_names - db_col_names
        for col_name in sorted(extra_columns):
            issues.append(
                {
                    "type": "extra_column",
                    "table": table,
                    "column": col_name,
                    "message": f"Column '{col_name}' documented in catalog but does not exist in database",
                }
            )

        # Check columns that exist in both
        common_columns = db_col_names & catalog_col_names

        for col_name in sorted(common_columns):
            db_col = db_col_map[col_name]
            catalog_col = catalog_col_map[col_name]

            # Check order
            if db_col["order"] != catalog_col["order"]:
                issues.append(
                    {
                        "type": "order_mismatch",
                        "table": table,
                        "column": col_name,
                        "db_value": db_col["order"],
                        "catalog_value": catalog_col["order"],
                        "message": f"Order mismatch for '{col_name}': DB={db_col['order']}, Catalog={catalog_col['order']}",
                    }
                )

            # Check type (normalize for comparison)
            db_type = db_col["type"].upper()
            catalog_type = catalog_col["type"].upper()

            # SERIAL is INTEGER at storage level; information_schema returns INTEGER for SERIAL columns
            # Treat SERIAL and INTEGER as equivalent so catalog can document DDL (SERIAL)
            types_match = (db_type == catalog_type) or (
                {db_type, catalog_type} == {"INTEGER", "SERIAL"}
            )

            if not types_match:
                issues.append(
                    {
                        "type": "type_mismatch",
                        "table": table,
                        "column": col_name,
                        "db_value": db_type,
                        "catalog_value": catalog_type,
                        "message": f"Type mismatch for '{col_name}': DB={db_type}, Catalog={catalog_type}",
                    }
                )

            # Check nullability (if catalog has a value - it's now nullable)
            if (
                catalog_col["nullable"] is not None
                and db_col["nullable"] != catalog_col["nullable"]
            ):
                issues.append(
                    {
                        "type": "nullability_mismatch",
                        "table": table,
                        "column": col_name,
                        "db_value": db_col["nullable"],
                        "catalog_value": catalog_col["nullable"],
                        "message": f"Nullability mismatch for '{col_name}': DB={db_col['nullable']}, Catalog={catalog_col['nullable']}",
                    }
                )

            # Check primary key (if catalog has a value - it's nullable)
            if (
                catalog_col["primary_key"] is not None
                and db_col["primary_key"] != catalog_col["primary_key"]
            ):
                issues.append(
                    {
                        "type": "primary_key_mismatch",
                        "table": table,
                        "column": col_name,
                        "db_value": db_col["primary_key"],
                        "catalog_value": catalog_col["primary_key"],
                        "message": f"Primary key mismatch for '{col_name}': DB={db_col['primary_key']}, Catalog={catalog_col['primary_key']}",
                    }
                )

            # Check foreign key (if catalog has a value)
            # Note: We only report FK issues if catalog says there SHOULD be a FK but DB doesn't have it
            # Missing FKs in test schema are acceptable (test data may not have constraints)
            db_fk = db_col.get("foreign_key")
            catalog_fk = catalog_col.get("foreign_key")

            # Only report FK mismatch if:
            # 1. Catalog documents a FK but DB has a different one (actual mismatch)
            # 2. DB has a FK that's not documented (missing in catalog)
            if db_fk and catalog_fk and db_fk != catalog_fk:
                issues.append(
                    {
                        "type": "foreign_key_mismatch",
                        "table": table,
                        "column": col_name,
                        "db_value": db_fk,
                        "catalog_value": catalog_fk,
                        "message": f"Foreign key mismatch for '{col_name}': DB={db_fk}, Catalog={catalog_fk}",
                    }
                )
            elif db_fk and not catalog_fk:
                issues.append(
                    {
                        "type": "foreign_key_missing_in_catalog",
                        "table": table,
                        "column": col_name,
                        "db_value": db_fk,
                        "message": f"Foreign key exists in DB but not documented in catalog for '{col_name}': {db_fk}",
                    }
                )
            # Note: We don't report when catalog has FK but DB doesn't - this is common for test schemas

    # Build response
    is_valid = len(issues) == 0

    logger.info(f"validate_data_catalog completed: {len(issues)} issues found")
    return {
        "status": "success" if is_valid else "validation_errors",
        "valid": is_valid,
        "message": "Catalog is valid" if is_valid else f"Found {len(issues)} validation issues",
        "issues": issues,
        "total_issues": len(issues),
        "tables_checked": len(common_tables),
        "total_db_tables": len(db_tables),
        "total_catalog_tables": len(catalog_tables),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate data catalog")
    parser.parse_args()
    result = validate_data_catalog()
    print(json.dumps(result, indent=2))
