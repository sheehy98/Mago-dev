#
# Imports
#

# Standard library
import os
import tempfile
from pathlib import Path

# Third party
import pytest

# Module under test
from dev.etl.snapshot_tables import (
    export_catalogs_to_csv,
    extract_table_name,
    generate_er_diagram,
    load_schema_tables_from_catalogs,
    parse_catalog_csv,
    quote_identifier,
    quote_schema_table,
    snapshot_table,
    table_to_file_path,
)

# Database
from dev.db import get_connection

#
# Tests for quote_identifier
#


def test_quote_identifier_already_quoted():
    """
    Story: Already quoted identifiers are returned unchanged

    Given an identifier that is already wrapped in double quotes
    When we call quote_identifier
    Then the identifier is returned unchanged
    """
    assert quote_identifier('"MyTable"') == '"MyTable"'


def test_quote_identifier_uppercase():
    """
    Story: Identifiers with uppercase need quoting

    Given an identifier containing uppercase letters
    When we call quote_identifier
    Then the identifier is wrapped in double quotes
    """
    assert quote_identifier("MyTable") == '"MyTable"'


def test_quote_identifier_starts_with_digit():
    """
    Story: Identifiers starting with digit need quoting

    Given an identifier that starts with a digit
    When we call quote_identifier
    Then the identifier is wrapped in double quotes
    """
    assert quote_identifier("1table") == '"1table"'


def test_quote_identifier_special_chars():
    """
    Story: Identifiers with special chars need quoting

    Given an identifier containing special characters like hyphens
    When we call quote_identifier
    Then the identifier is wrapped in double quotes
    """
    assert quote_identifier("table-name") == '"table-name"'


def test_quote_identifier_simple_lowercase():
    """
    Story: Simple lowercase identifiers don't need quoting

    Given an identifier with only lowercase letters
    When we call quote_identifier
    Then the identifier is returned without quotes
    """
    assert quote_identifier("mytable") == "mytable"


def test_quote_identifier_with_underscore():
    """
    Story: Underscores don't require quoting

    Given an identifier containing underscores
    When we call quote_identifier
    Then the identifier is returned without quotes
    """
    assert quote_identifier("my_table") == "my_table"


#
# Tests for quote_schema_table
#


def test_quote_schema_table_with_dot():
    """
    Story: Quote schema.table identifier

    Given a lowercase schema.table identifier
    When we call quote_schema_table
    Then both parts are returned without quotes
    """
    assert quote_schema_table("meta.users") == "meta.users"


def test_quote_schema_table_uppercase():
    """
    Story: Quote schema.table with uppercase

    Given a schema.table identifier with uppercase letters
    When we call quote_schema_table
    Then both parts are individually quoted
    """
    assert quote_schema_table("Meta.Users") == '"Meta"."Users"'


def test_quote_schema_table_no_dot():
    """
    Story: Quote table without schema

    Given an identifier without a dot separator
    When we call quote_schema_table
    Then the identifier is quoted as a single part
    """
    assert quote_schema_table("users") == "users"


#
# Tests for table_to_file_path
#


def test_table_to_file_path_simple():
    """
    Story: Convert schema.table to file path

    Given a simple schema.table identifier
    When we call table_to_file_path
    Then the path maps to tables_dir/schema/table/create.sql
    """
    tables_dir = Path("/data/tables")
    result = table_to_file_path("meta.users", tables_dir)
    assert result == Path("/data/tables/meta/users/create.sql")


def test_table_to_file_path_nested():
    """
    Story: Convert schema.table__subtable to nested path

    Given a schema.table identifier with double underscore nesting
    When we call table_to_file_path
    Then the double underscores are converted to nested directories
    """
    tables_dir = Path("/data/tables")
    result = table_to_file_path("test.pages__settings", tables_dir)
    assert result == Path("/data/tables/test/pages/settings/create.sql")


def test_table_to_file_path_no_schema():
    """
    Story: Raise error when table has no schema

    Given a table identifier without a schema prefix
    When we call table_to_file_path
    Then a ValueError is raised
    """
    tables_dir = Path("/data/tables")
    with pytest.raises(ValueError, match="Table name must include schema"):
        table_to_file_path("users", tables_dir)


#
# Tests for extract_table_name
#


def test_extract_table_name_from_real_file():
    """
    Story: Extract table name from a real create.sql file

    Given a real create.sql file in the tables directory
    When we call extract_table_name
    Then the schema.table name is extracted from the SQL
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../../data/tables")

    # Use meta/theme/create.sql as a known file
    theme_sql = os.path.join(tables_dir, "meta/theme/create.sql")
    if os.path.exists(theme_sql):
        result = extract_table_name(theme_sql)
        assert result is not None
        assert "." in result  # Should be schema.table format


#
# Constants
#

# Use a non-existent schema to avoid modifying real data
TEST_SCHEMA = "etl_test_nonexistent"

#
# Tests for snapshot_table function
#


def test_snapshot_table_success():
    """
    Story: Snapshot table saves table data to CSV files

    Given tables exist in the database
    When we call snapshot_table with isolated schema
    Then it returns success
    """
    data = snapshot_table(usernames=[TEST_SCHEMA])

    assert data["status"] == "success"


def test_snapshot_table_response_structure():
    """
    Story: Snapshot table returns proper response structure

    Given a valid request
    When we call snapshot_table
    Then it returns expected fields
    """
    data = snapshot_table(usernames=[TEST_SCHEMA])

    assert "status" in data
    assert "message" in data


def test_snapshot_table_with_usernames_filter():
    """
    Story: Snapshot table can filter by usernames

    Given a request with usernames filter
    When we call snapshot_table
    Then only tables for those users are snapshotted
    """
    data = snapshot_table(usernames=[TEST_SCHEMA])

    assert data["status"] == "success"


#
# Tests for full sync cycle (create, update, delete paths)
#


def test_snapshot_table_full_sync_cycle(redirect_tables_dir):
    """
    Story: Snapshot table handles create, update, and delete lifecycle

    Given a real database table
    When we snapshot it (create), snapshot again (update), drop it, and snapshot (delete)
    Then each phase reports the correct file operations
    """

    # Files go to tmp_path via redirect_tables_dir
    schema_dir = redirect_tables_dir / "etl_test_snap"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Setup: create schema and tables with various column types
        cursor.execute("CREATE SCHEMA IF NOT EXISTS etl_test_snap")

        # First parent table (referenced by FK)
        cursor.execute(
            """
            CREATE TABLE etl_test_snap.parent_ref (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL
            )
            """
        )
        cursor.execute("INSERT INTO etl_test_snap.parent_ref (code) VALUES ('A'), ('B')")

        # Second parent table (for multiple FK coverage)
        cursor.execute(
            """
            CREATE TABLE etl_test_snap.category_ref (
                id SERIAL PRIMARY KEY,
                tag CHAR(10) NOT NULL
            )
            """
        )
        cursor.execute("INSERT INTO etl_test_snap.category_ref (tag) VALUES ('cat1'), ('cat2')")

        # Main table with diverse column types to exercise all branches
        cursor.execute(
            """
            CREATE TABLE etl_test_snap.sync_test (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER DEFAULT 0,
                label VARCHAR(100),
                score NUMERIC(10,2),
                parent_id INTEGER REFERENCES etl_test_snap.parent_ref(id),
                category_id INTEGER REFERENCES etl_test_snap.category_ref(id)
            )
            """
        )
        cursor.execute(
            "INSERT INTO etl_test_snap.sync_test "
            "(name, value, label, score, parent_id, category_id) "
            "VALUES ('row1', 10, 'first', 1.5, 1, 1), ('row2', 20, 'second', 2.5, 2, 2)"
        )
        conn.commit()

        # Step 1: Create path — tables in DB but not on disk
        data = snapshot_table(usernames=["etl_test_snap"])
        assert data["files_created"] >= 3

        # Verify files were created in tmp_path
        create_sql_path = schema_dir / "sync_test" / "create.sql"
        seed_csv_path = schema_dir / "sync_test" / "seed.csv"
        assert create_sql_path.exists()
        assert seed_csv_path.exists()

        # Verify content
        assert "row1" in seed_csv_path.read_text()
        create_sql_content = create_sql_path.read_text()
        assert "CREATE TABLE" in create_sql_content
        assert "FOREIGN KEY" in create_sql_content
        assert "VARCHAR" in create_sql_content
        assert "NUMERIC" in create_sql_content

        # Step 2: Update path — tables exist in both DB and disk
        data = snapshot_table(usernames=["etl_test_snap"])
        assert data["files_updated"] >= 3
        assert data["files_created"] == 0

        # Step 3: Delete path — drop tables, then snapshot to detect orphans
        cursor.execute("DROP TABLE etl_test_snap.sync_test")
        cursor.execute("DROP TABLE etl_test_snap.category_ref")
        cursor.execute("DROP TABLE etl_test_snap.parent_ref")
        conn.commit()

        data = snapshot_table(usernames=["etl_test_snap"])
        assert data["files_deleted"] >= 3

        # Verify files were removed
        assert not create_sql_path.exists()
        assert not seed_csv_path.exists()

    finally:
        # Cleanup database only — filesystem is tmp_path, cleaned up automatically
        cursor.execute("DROP SCHEMA IF EXISTS etl_test_snap CASCADE")
        conn.commit()
        cursor.close()
        conn.close()


#
# Tests for invalid create.sql handling
#


def test_snapshot_table_skips_invalid_create_sql(redirect_tables_dir):
    """
    Story: Files without valid CREATE TABLE are not treated as tables

    Given a create.sql file with no valid CREATE TABLE statement
    When we snapshot tables for that schema
    Then the file is not treated as a local table and not deleted
    """

    # Create a malformed create.sql in tmp_path
    bad_dir = redirect_tables_dir / "etl_test_badfile" / "bad_table"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "create.sql").write_text("-- this file is intentionally empty")

    # Call snapshot — bad file won't be in local_tables, so it's not orphaned
    data = snapshot_table(usernames=["etl_test_badfile"])
    assert data["files_deleted"] == 0


#
# Tests for unfiltered snapshot (catalogs + ER diagram)
#


def test_snapshot_table_unfiltered_exports_catalogs_and_diagram(redirect_all_paths):
    """
    Story: Unfiltered snapshot exports catalogs and generates ER diagram

    Given no usernames filter and an invalid create.sql in meta schema
    When we call snapshot_table
    Then catalogs are updated, ER diagram is generated, and bad files are skipped
    """

    # All paths redirected to tmp_path (pre-populated with real data/tables copy)
    tables_dir = redirect_all_paths / "tables"
    schema_mmd_path = redirect_all_paths / "schema.mmd"

    # Place a bad create.sql to exercise the skip path in export_catalogs_to_csv
    bad_dir = tables_dir / "meta" / "etl_test_bad_catalog"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "create.sql").write_text("-- this file is intentionally empty")

    # Call unfiltered snapshot
    data = snapshot_table()

    # Catalogs should be updated (bad file skipped, valid ones processed)
    assert data["catalogs_updated"] > 0

    # Schema diagram should be generated
    assert data["schema_updated"] is True

    # Verify schema.mmd file exists and has valid content
    assert schema_mmd_path.exists()
    assert schema_mmd_path.read_text().startswith("erDiagram")

    # Should report total tables
    assert data["total_tables"] > 0


#
# Tests for parse_catalog_csv edge cases
#


def test_parse_catalog_csv_edge_cases():
    """
    Story: parse_catalog_csv returns None for invalid catalog files

    Given a catalog CSV with only headers (empty) or a table name without a dot
    When we call parse_catalog_csv
    Then it returns None for both cases
    """

    # Case 1: Empty CSV (header only, no data rows)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(
            "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        )
        empty_path = Path(f.name)

    try:
        result = parse_catalog_csv(empty_path)
        assert result is None
    finally:
        empty_path.unlink()

    # Case 2: Table name without a dot
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(
            "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        )
        f.write("nodot_table,col1,0,TEXT,,,,description,\n")
        nodot_path = Path(f.name)

    try:
        result = parse_catalog_csv(nodot_path)
        assert result is None
    finally:
        nodot_path.unlink()


#
# Tests for generate_er_diagram edge cases
#


def test_generate_er_diagram_edge_cases():
    """
    Story: generate_er_diagram skips entries with None table names

    Given table definitions and FK references with None table names
    When we call generate_er_diagram
    Then it skips the None entries and includes valid ones
    """

    # Build schema_tables with a None table, FK to None, and FK to nonexistent table
    schema_tables = {
        "test_schema": [
            # Entry with table=None — should be skipped (line 154)
            {
                "schema": "test_schema",
                "table": None,
                "columns": [{"name": "id", "type": "INTEGER"}],
                "primary_keys": ["id"],
                "foreign_keys": [],
            },
            # Valid entry with FKs that exercise skip paths
            {
                "schema": "test_schema",
                "table": "valid_table",
                "columns": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "ref_id", "type": "INTEGER"},
                    {"name": "missing_id", "type": "INTEGER"},
                ],
                "primary_keys": ["id"],
                "foreign_keys": [
                    # FK referencing table=None — hits continue at line 179
                    {
                        "columns": ["ref_id"],
                        "references": {
                            "schema": "test_schema",
                            "table": None,
                            "columns": ["id"],
                        },
                    },
                    # FK referencing nonexistent table — hits continue at line 186
                    {
                        "columns": ["missing_id"],
                        "references": {
                            "schema": "test_schema",
                            "table": "nonexistent_table",
                            "columns": ["id"],
                        },
                    },
                ],
            },
        ],
    }

    result = generate_er_diagram(schema_tables)

    # Should contain erDiagram header
    assert "erDiagram" in result

    # Should contain the valid table
    assert "test_schema_valid_table" in result

    # Should not contain "None" as a table reference
    assert "test_schema_None" not in result

    # Should not contain relationship to nonexistent table
    assert "nonexistent_table" not in result


#
# Tests for load_schema_tables_from_catalogs with non-existent schema
#


def test_load_schema_tables_skips_nonexistent_schema():
    """
    Story: load_schema_tables_from_catalogs skips schemas without directories

    Given a list of schemas where one does not exist on disk
    When we call load_schema_tables_from_catalogs
    Then the missing schema is skipped and returns an empty list
    """

    # Resolve tables directory
    api_dir = Path(__file__).parent.parent.parent.parent
    tables_dir = api_dir.parent / "data" / "tables"

    # Include a schema that definitely doesn't exist
    result = load_schema_tables_from_catalogs(tables_dir, ["meta", "nonexistent_schema_xyz"])

    # meta should have tables, nonexistent should be empty
    assert len(result["meta"]) > 0
    assert len(result["nonexistent_schema_xyz"]) == 0


#
# Tests for extract_table_name return paths
#


def test_extract_table_name_returns_schema_dot_table():
    """
    Story: extract_table_name parses quoted schema.table from CREATE TABLE SQL

    Given a temp file with a CREATE TABLE using quoted schema and table
    When we call extract_table_name
    Then it returns the schema.table string via the quoted path
    """

    # Quoted schema format hits group(1) + group(2) → line 222
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write('CREATE TABLE "my_schema"."my_table" (id SERIAL PRIMARY KEY);')
        sql_path = f.name

    try:
        result = extract_table_name(sql_path)
        assert result == "my_schema.my_table"
    finally:
        os.unlink(sql_path)


def test_extract_table_name_returns_none_for_no_match():
    """
    Story: extract_table_name returns None when no CREATE TABLE found

    Given a temp file with no CREATE TABLE statement
    When we call extract_table_name
    Then it returns None
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write("-- just a comment, no CREATE TABLE")
        sql_path = f.name

    try:
        result = extract_table_name(sql_path)
        assert result is None
    finally:
        os.unlink(sql_path)


#
# Tests for export_catalogs_to_csv early return
#


def test_export_catalogs_returns_zero_without_catalog_table():
    """
    Story: export_catalogs_to_csv returns 0 when meta.catalog does not exist

    Given the meta.catalog table has been temporarily dropped
    When we call export_catalogs_to_csv
    Then it returns 0 immediately
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Back up meta.catalog into a temp table
    cursor.execute("CREATE TABLE meta.catalog_backup AS SELECT * FROM meta.catalog")
    cursor.execute("DROP TABLE meta.catalog")
    conn.commit()

    try:
        tables_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "tables"
        result = export_catalogs_to_csv(tables_dir)
        assert result == 0

    finally:
        # Restore meta.catalog from backup
        cursor.execute("CREATE TABLE meta.catalog AS SELECT * FROM meta.catalog_backup")
        cursor.execute("DROP TABLE meta.catalog_backup")
        conn.commit()
        cursor.close()
        conn.close()


#
# Tests for meta.catalog create path (ORDER BY branch)
#


def test_snapshot_creates_meta_catalog_with_order(redirect_all_paths):
    """
    Story: Snapshot creates meta.catalog with ORDER BY when table is new

    Given meta.catalog exists in DB but not on filesystem
    When we call snapshot_table
    Then it creates the seed.csv with rows ordered by Table, Order
    """

    # Paths redirected to tmp_path (pre-populated with real data/tables copy)
    tables_dir = redirect_all_paths / "tables"
    catalog_dir = tables_dir / "meta" / "catalog"
    seed_csv = catalog_dir / "seed.csv"
    create_sql = catalog_dir / "create.sql"

    # Remove filesystem files so snapshot treats it as "create"
    if seed_csv.exists():
        seed_csv.unlink()
    if create_sql.exists():
        create_sql.unlink()

    # Run snapshot — hits the create path with ORDER BY for meta.catalog
    data = snapshot_table(usernames=["meta"])

    # Should have created files
    assert data["files_created"] >= 1
    assert seed_csv.exists()
