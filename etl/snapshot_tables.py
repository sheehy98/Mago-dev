#
# Imports
#

# Standard library
import argparse
import csv
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# Database functions
from dev.db import execute_query

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#


def sanitize_name(name: str) -> str:
    """Convert names with spaces/special chars to valid Mermaid identifiers"""
    sanitized = name.replace(" ", "_")
    return "".join(c if c.isalnum() or c == "_" else "" for c in sanitized)


def format_column_type(col: dict[str, Any]) -> str:
    """Format column type for Mermaid diagram"""
    col_type = col.get("type", "TEXT")
    if col_type.startswith("NUMERIC"):
        return "DECIMAL"
    elif col_type.startswith("TIMESTAMP"):
        return "TIMESTAMP"
    return col_type


def generate_entity_definition(schema: str, table: str, columns: list[dict[str, Any]]) -> str:
    """Generate Mermaid entity definition"""
    entity_name = f"{schema}_{table}"
    lines = [f"    {entity_name} {{"]
    for col in columns:
        col_name = sanitize_name(col["name"])
        col_type = format_column_type(col)
        lines.append(f"        {col_type} {col_name}")
    lines.append("    }")
    return "\n".join(lines)


def parse_catalog_csv(catalog_path: Path) -> Optional[dict[str, Any]]:
    """Parse catalog.csv to extract table definition"""
    with open(catalog_path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return None

    # First row (Order=0) contains table name
    table_full_name = rows[0].get("Table", "")
    if not table_full_name or "." not in table_full_name:
        return None

    schema, table_name = table_full_name.split(".", 1)

    columns = []
    primary_keys = []
    foreign_keys_map = {}

    # Parse column rows (Order >= 1)
    for row in rows:
        if row.get("Order", "0") == "0":
            continue

        col_name = row.get("Column", "")
        col_type = row.get("Type", "TEXT")

        # Parse Primary Key
        pk_str = row.get("Primary Key?", "").strip().upper()
        if pk_str == "TRUE":
            primary_keys.append(col_name)

        # Parse Foreign Key (format: schema.table.column)
        fk_str = row.get("Foreign Key", "").strip()
        if fk_str:
            foreign_keys_map[col_name] = fk_str

        columns.append({"name": col_name, "type": col_type})

    # Build foreign_keys list
    foreign_keys = []
    for fk_col, fk_ref in foreign_keys_map.items():
        parts = fk_ref.split(".")
        if len(parts) == 3:
            ref_schema, ref_table, ref_column = parts
            foreign_keys.append(
                {
                    "columns": [fk_col],
                    "references": {
                        "schema": ref_schema,
                        "table": ref_table,
                        "columns": [ref_column],
                    },
                }
            )

    return {
        "schema": schema,
        "table": table_name,
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
    }


def load_schema_tables_from_catalogs(tables_dir: Path, schemas: list[str]) -> dict[str, list[dict]]:
    """Load table definitions from catalog.csv files"""
    schema_tables = {schema: [] for schema in schemas}

    for schema in schemas:
        schema_dir = tables_dir / schema
        if not schema_dir.exists():
            continue

        for catalog_path in schema_dir.rglob("catalog.csv"):
            table_def = parse_catalog_csv(catalog_path)
            if table_def and table_def.get("schema") == schema:
                schema_tables[schema].append(table_def)

    return schema_tables


def generate_er_diagram(schema_tables: dict[str, list[dict]]) -> str:
    """Generate Mermaid ER diagram from table definitions"""
    lines = ["erDiagram", ""]
    all_tables = {}
    relationship_keys = set()

    # Generate entity definitions
    for schema, tables in schema_tables.items():
        lines.append(f"    %% {schema.capitalize()} Schema")
        lines.append("")

        for table_def in tables:
            schema_name = table_def.get("schema", schema)
            table_name = table_def.get("table")
            columns = table_def.get("columns", [])

            if not table_name:
                continue

            entity_def = generate_entity_definition(schema_name, table_name, columns)
            lines.append(entity_def)
            lines.append("")

            full_table_name = f"{schema_name}_{table_name}"
            all_tables[full_table_name] = {
                "schema": schema_name,
                "table": table_name,
                "foreign_keys": table_def.get("foreign_keys", []),
                "primary_keys": table_def.get("primary_keys", []),
            }

    # Generate relationships
    lines.append("    %% Relationships")
    lines.append("")

    for full_table_name, table_info in all_tables.items():
        for fk in table_info.get("foreign_keys", []):
            ref_schema = fk["references"].get("schema")
            ref_table = fk["references"].get("table")
            fk_cols = fk.get("columns", [])

            if not ref_table:
                continue

            ref_full_name = (
                f"{ref_schema}_{ref_table}" if ref_schema else f"{table_info['schema']}_{ref_table}"
            )

            if ref_full_name not in all_tables:
                continue

            label = fk_cols[0] if fk_cols else "references"
            ref_primary_keys = all_tables[ref_full_name].get("primary_keys", [])
            ref_cols = fk["references"].get("columns", [])
            is_primary = len(ref_cols) > 0 and ref_cols[0] in ref_primary_keys
            cardinality = "||--o{" if is_primary else "}o--||"

            relationship_key = (full_table_name, ref_full_name, label)
            if relationship_key not in relationship_keys:
                relationship_keys.add(relationship_key)
                lines.append(f'    {full_table_name} {cardinality} {ref_full_name} : "{label}"')

    return "\n".join(lines)


def extract_table_name(sql_file: str) -> Optional[str]:
    """Extract table name from create.sql file"""
    with open(sql_file) as f:
        content = f.read()

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


def quote_schema_table(table_name: str) -> str:
    """Quote schema.table identifier"""
    if "." in table_name:
        schema, table = table_name.split(".", 1)
        return f"{quote_identifier(schema)}.{quote_identifier(table)}"
    return quote_identifier(table_name)


def list_all_tables() -> set[str]:
    """Query PostgreSQL to get all tables (schema.table format)"""
    query = """
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schemaname, tablename;
    """

    result = execute_query(query)
    tables = set()

    for row in result["rows"]:
        tables.add(f"{row[0]}.{row[1]}")

    return tables


def table_to_file_path(table_name: str, tables_dir: Path) -> Path:
    """Convert schema.table to filesystem path (__ maps to /)"""
    if "." not in table_name:
        raise ValueError(f"Table name must include schema: {table_name}")

    schema, table = table_name.split(".", 1)
    path_parts = table.split("__")

    file_path = tables_dir / schema
    for part in path_parts:
        file_path = file_path / part
    file_path = file_path / "create.sql"

    return file_path


def get_local_tables(tables_dir: Path) -> set[str]:
    """Scan filesystem for all create.sql files and extract table names"""
    local_tables = set()

    for sql_file in tables_dir.rglob("create.sql"):
        table_name = extract_table_name(str(sql_file))
        if table_name:
            local_tables.add(table_name)

    return local_tables


def export_catalogs_to_csv(tables_dir: Path) -> int:
    """Export catalog data from meta.catalog to catalog.csv files"""

    # Check if meta.catalog exists
    check_result = execute_query(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'meta' AND table_name = 'catalog'
        """
    )
    if not check_result["rows"]:
        return 0

    catalogs_updated = 0

    # Find all create.sql files in meta and test schemas
    meta_test_sql_files = []
    for schema in ["meta", "test00000000000000000000"]:
        schema_dir = tables_dir / schema
        if schema_dir.exists():
            for sql_file in schema_dir.rglob("create.sql"):
                meta_test_sql_files.append(str(sql_file))

    for sql_file in meta_test_sql_files:
        table_name = extract_table_name(sql_file)
        if not table_name:
            continue

        sql_path = Path(sql_file)
        catalog_csv_path = sql_path.parent / "catalog.csv"

        # Query meta.catalog for this table's rows
        query = """
            SELECT "Table", "Column", "Order", "Type", "Nullable?", "Primary Key?",
                   "Foreign Key", "Description", "Sample Values"
            FROM meta.catalog WHERE "Table" = %s ORDER BY "Order"
        """
        result = execute_query(query, (table_name,))

        # Write catalog.csv
        with open(catalog_csv_path, "w", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(
                [
                    "Table",
                    "Column",
                    "Order",
                    "Type",
                    "Nullable?",
                    "Primary Key?",
                    "Foreign Key",
                    "Description",
                    "Sample Values",
                ]
            )
            for row in result["rows"]:
                nullable_str = "TRUE" if row[4] is True else ("FALSE" if row[4] is False else "")
                pk_str = "TRUE" if row[5] is True else ("FALSE" if row[5] is False else "")
                column_str = "NULL" if row[1] is None else row[1]
                fk_str = row[6] or ""
                writer.writerow(
                    [
                        row[0],
                        column_str,
                        row[2],
                        row[3],
                        nullable_str,
                        pk_str,
                        fk_str,
                        row[7] or "",
                        row[8] or "",
                    ]
                )

        catalogs_updated += 1

    return catalogs_updated


def generate_create_table_statement(schema: str, table: str) -> str:
    """Generate CREATE TABLE statement from information_schema"""

    # Query columns
    columns_result = execute_query(
        """
        SELECT column_name, data_type, udt_name, is_nullable, column_default,
               character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position;
        """,
        (schema, table),
    )

    # Query primary key
    pk_result = execute_query(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s
        ORDER BY kcu.ordinal_position;
        """,
        (schema, table),
    )
    pk_columns = list(dict.fromkeys([row[0] for row in pk_result["rows"]]))

    # Query unique constraints (single-column only)
    unique_result = execute_query(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = %s AND tc.table_name = %s
        AND (SELECT COUNT(*) FROM information_schema.key_column_usage kcu2
             WHERE kcu2.constraint_name = tc.constraint_name) = 1;
        """,
        (schema, table),
    )
    unique_columns = {row[0] for row in unique_result["rows"]}

    # Query foreign keys
    fk_result = execute_query(
        """
        SELECT kcu.column_name, ccu.table_schema, ccu.table_name, ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name AND ccu.constraint_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s AND tc.table_name = %s;
        """,
        (schema, table),
    )

    # Deduplicate foreign keys
    fks_by_column = defaultdict(list)
    for fk_row in fk_result["rows"]:
        fks_by_column[fk_row[0]].append((fk_row[1], fk_row[2], fk_row[3]))

    # Build CREATE TABLE statement
    lines = []
    quoted_schema = quote_identifier(schema)
    full_table_name = quote_schema_table(f"{schema}.{table}")

    lines.append("-- Schema Creation")
    lines.append(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema};")
    lines.append("")
    lines.append("-- Table Creation")
    lines.append(f"CREATE TABLE {full_table_name} (")
    lines.append("")
    lines.append("    -- Columns")

    # Build column definitions
    column_defs = []
    for col_row in columns_result["rows"]:
        col_name, data_type, udt_name, is_nullable, col_default = col_row[:5]
        char_max_len, num_precision, num_scale = col_row[5:8]

        quoted_col = quote_identifier(col_name)
        pg_type = data_type.upper() if data_type else udt_name.upper()

        # Check for SERIAL
        is_serial = False
        if col_default and "nextval" in col_default.lower() and pg_type == "INTEGER":
            pg_type = "SERIAL"
            is_serial = True

        # Format type
        if pg_type in ["CHARACTER VARYING", "VARCHAR"]:
            pg_type = f"VARCHAR({char_max_len})" if char_max_len else "TEXT"
        elif pg_type == "NUMERIC" and num_precision:
            pg_type = (
                f"NUMERIC({num_precision},{num_scale})"
                if num_scale
                else f"NUMERIC({num_precision})"
            )
        elif pg_type in ["CHARACTER", "CHAR"]:
            pg_type = "TEXT"

        col_def = f"    {quoted_col} {pg_type}"

        if is_nullable != "YES":
            col_def += " NOT NULL"
        if col_name in unique_columns:
            col_def += " UNIQUE"
        if col_default and not is_serial:
            col_def += f" DEFAULT {col_default}"

        col_def += ","
        column_defs.append(col_def)

    lines.extend(column_defs)
    lines.append("")
    lines.append("    -- Primary Key")

    if pk_columns:
        quoted_pk_cols = [quote_identifier(col) for col in pk_columns]
        pk_def = f'    PRIMARY KEY ({", ".join(quoted_pk_cols)})'
        if fk_result["rows"]:
            pk_def += ","
        lines.append(pk_def)

    # Foreign keys
    if fk_result["rows"]:
        lines.append("")
        lines.append("    -- Foreign Keys")
        fk_defs = []
        seen_fks = set()

        for fk_row in fk_result["rows"]:
            col_name, fk_schema, fk_table, fk_col = fk_row
            quoted_col = quote_identifier(col_name)
            quoted_fk_schema = quote_identifier(fk_schema)
            quoted_fk_table = quote_identifier(fk_table)
            quoted_fk_col = quote_identifier(fk_col)

            fk_def = f"    FOREIGN KEY ({quoted_col}) REFERENCES {quoted_fk_schema}.{quoted_fk_table} ({quoted_fk_col})"
            if fk_def not in seen_fks:
                seen_fks.add(fk_def)
                fk_defs.append(fk_def)

        for i, fk_def in enumerate(fk_defs):
            if i < len(fk_defs) - 1:
                fk_defs[i] = fk_def + ","
        lines.extend(fk_defs)

    lines.append("")
    lines.append(");")

    return "\n".join(lines) + "\n"


#
# Handler Functions
#


def snapshot_table(usernames: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Sync database tables with local filesystem

    @param usernames (Optional[list[str]]): Filter by specific usernames/schemas
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("snapshot_table called")

    # Get tables directory
    from dev.paths import TABLES_DIR
    tables_dir = TABLES_DIR

    # Track statistics
    files_created = 0
    files_deleted = 0
    files_updated = 0

    # Get tables from database and filesystem
    db_tables = list_all_tables()
    local_tables = get_local_tables(tables_dir)

    # Filter by usernames if specified
    if usernames:
        db_tables = {t for t in db_tables if t.split(".")[0] in usernames}
        local_tables = {t for t in local_tables if t.split(".")[0] in usernames}

    tables_to_delete = local_tables - db_tables
    tables_to_create = db_tables - local_tables
    tables_to_update = db_tables & local_tables

    # Delete orphaned files
    for table_name in tables_to_delete:
        create_sql_path = table_to_file_path(table_name, tables_dir)
        seed_csv_path = create_sql_path.parent / "seed.csv"

        if create_sql_path.exists():
            create_sql_path.unlink()
            files_deleted += 1
        if seed_csv_path.exists():
            seed_csv_path.unlink()
            files_deleted += 1

    # Create new files for missing tables
    for table_name in tables_to_create:
        schema, table = table_name.split(".", 1)
        create_sql_path = table_to_file_path(table_name, tables_dir)
        seed_csv_path = create_sql_path.parent / "seed.csv"

        create_sql_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate CREATE TABLE
        create_statement = generate_create_table_statement(schema, table)
        with open(create_sql_path, "w") as f:
            f.write(create_statement)

        # Export data to seed.csv (order catalog for consistency)
        quoted_table = quote_schema_table(table_name)
        if table_name == "meta.catalog":
            result = execute_query(f'SELECT * FROM {quoted_table} ORDER BY "Table", "Order";')
        else:
            result = execute_query(f"SELECT * FROM {quoted_table};")

        with open(seed_csv_path, "w", newline="") as f:
            if result["columns"]:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(result["columns"])
                for row in result["rows"]:
                    writer.writerow(row)

        files_created += 1

    # Update existing tables (export data to seed.csv)
    for table_name in tables_to_update:
        create_sql_path = table_to_file_path(table_name, tables_dir)
        seed_csv_path = create_sql_path.parent / "seed.csv"

        # Ensure directory exists (table name in SQL may not match file path)
        create_sql_path.parent.mkdir(parents=True, exist_ok=True)

        quoted_table = quote_schema_table(table_name)
        if table_name == "meta.catalog":
            result = execute_query(f'SELECT * FROM {quoted_table} ORDER BY "Table", "Order";')
        else:
            result = execute_query(f"SELECT * FROM {quoted_table};")

        with open(seed_csv_path, "w", newline="") as f:
            if result["columns"]:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(result["columns"])
                for row in result["rows"]:
                    writer.writerow(row)

        files_updated += 1

    # Export catalog data (only if no filter - full snapshot)
    catalogs_updated = 0
    if not usernames:
        catalogs_updated = export_catalogs_to_csv(tables_dir)

    # Generate schema diagram (only if no filter - full snapshot)
    schema_updated = False
    if not usernames:
        schemas = ["meta", "test00000000000000000000"]
        schema_tables = load_schema_tables_from_catalogs(tables_dir, schemas)
        mermaid_diagram = generate_er_diagram(schema_tables)

        from dev.paths import SCHEMA_MMD_PATH
        schema_mmd_path = SCHEMA_MMD_PATH
        with open(schema_mmd_path, "w") as f:
            f.write(mermaid_diagram.rstrip() + "\n")
        schema_updated = True

    logger.info(
        f"snapshot_table completed: {files_created} created, {files_updated} updated, "
        f"{files_deleted} deleted, {catalogs_updated} catalogs"
    )

    return {
        "status": "success",
        "message": f"Snapshot: {files_created} created, {files_updated} updated, "
        f"{files_deleted} deleted, {catalogs_updated} catalogs",
        "files_created": files_created,
        "files_updated": files_updated,
        "files_deleted": files_deleted,
        "catalogs_updated": catalogs_updated,
        "schema_updated": schema_updated,
        "total_tables": len(db_tables),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot database tables")
    parser.add_argument("--usernames", nargs="*", help="Filter by usernames/schemas")
    args = parser.parse_args()
    result = snapshot_table(usernames=args.usernames)
    print(json.dumps(result, indent=2))
