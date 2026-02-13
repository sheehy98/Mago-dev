#
# Imports
#

# Standard library
import os
import tempfile
from pathlib import Path

# Module under test
from dev.etl.create_tables import create_table
from dev.etl.drop_tables import drop_table
from dev.etl.seed_tables import (
    extract_table_name_from_create_sql,
    find_catalog_csv_files,
    find_seed_csv_files,
    has_serial_column,
    quote_identifier,
    quote_schema_table,
    reset_serial_sequence,
    seed_catalog_files,
    seed_table,
)

#
# Tests for find_seed_csv_files
#


def test_find_seed_csv_files_all():
    """
    Story: Find all seed.csv files in tables directory

    Given the tables directory exists with seed CSV files
    When we call find_seed_csv_files with no filter
    Then all seed.csv files are returned except meta/catalog
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_seed_csv_files(tables_dir)
    assert len(files) > 0
    assert all(f.endswith("seed.csv") for f in files)
    # Should exclude meta/catalog/seed.csv
    assert not any("meta/catalog/seed.csv" in f for f in files)


def test_find_seed_csv_files_with_usernames():
    """
    Story: Find seed.csv files only for specific usernames

    Given the tables directory exists with seed CSV files
    When we call find_seed_csv_files with a username filter
    Then only seed.csv files for that username are returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_seed_csv_files(tables_dir, usernames=["meta"])
    assert len(files) > 0
    assert all("meta" in f for f in files)


def test_find_seed_csv_files_nonexistent_username():
    """
    Story: Return empty list for nonexistent username

    Given a username that does not exist in the tables directory
    When we call find_seed_csv_files with that username
    Then an empty list is returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_seed_csv_files(tables_dir, usernames=["nonexistent_user_xyz"])
    assert files == []


#
# Tests for find_catalog_csv_files
#


def test_find_catalog_csv_files_default_schemas():
    """
    Story: Find catalog.csv files in default schemas

    Given the tables directory has catalog CSV files in meta and test user schemas
    When we call find_catalog_csv_files with no filter
    Then catalog.csv files from default schemas are returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_catalog_csv_files(tables_dir)
    assert len(files) > 0
    assert all(f.endswith("catalog.csv") for f in files)


def test_find_catalog_csv_files_specific_schema():
    """
    Story: Find catalog.csv files in specific schema

    Given the tables directory has catalog CSV files
    When we call find_catalog_csv_files with a schema filter
    Then only catalog.csv files for that schema are returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_catalog_csv_files(tables_dir, schemas=["meta"])
    assert len(files) > 0
    assert all("meta" in f for f in files)


def test_find_catalog_csv_files_nonexistent_schema():
    """
    Story: Return empty list for nonexistent schema

    Given a schema that does not exist in the tables directory
    When we call find_catalog_csv_files with that schema
    Then an empty list is returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_catalog_csv_files(tables_dir, schemas=["nonexistent_schema_xyz"])
    assert files == []


#
# Tests for extract_table_name_from_create_sql
#


def test_extract_table_name_from_create_sql():
    """
    Story: Extract table name from a real create.sql file

    Given a real create.sql file in the tables directory
    When we call extract_table_name_from_create_sql
    Then the schema.table name is extracted from the SQL
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    from dev.etl.create_tables import find_create_sql_files

    sql_files = find_create_sql_files(tables_dir, usernames=["meta"])
    if sql_files:
        table_name = extract_table_name_from_create_sql(sql_files[0])
        assert table_name is not None
        assert "." in table_name  # Should be schema.table format


def test_extract_table_name_nonexistent_file():
    """
    Story: Return None for nonexistent file

    Given a file path that does not exist
    When we call extract_table_name_from_create_sql
    Then None is returned
    """
    table_name = extract_table_name_from_create_sql("/nonexistent/path/create.sql")
    assert table_name is None


def test_extract_table_name_quoted_schema():
    """
    Story: Extract table name from SQL with quoted schema.table

    Given a create.sql file with quoted schema and table names
    When we call extract_table_name_from_create_sql
    Then the schema.table name is extracted without quotes
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write('CREATE TABLE "meta"."users" (id SERIAL);')
        f.flush()
        table_name = extract_table_name_from_create_sql(f.name)
        assert table_name == "meta.users"
        os.unlink(f.name)


def test_extract_table_name_no_match():
    """
    Story: Return None when SQL has no CREATE TABLE

    Given a SQL file without a CREATE TABLE statement
    When we call extract_table_name_from_create_sql
    Then None is returned
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write("SELECT * FROM users;")
        f.flush()
        table_name = extract_table_name_from_create_sql(f.name)
        assert table_name is None
        os.unlink(f.name)


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
# Tests for has_serial_column
#


def test_has_serial_column_with_serial():
    """
    Story: Detect SERIAL in create.sql

    Given a create.sql file that contains a SERIAL column
    When we call has_serial_column
    Then it returns True
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")

    # meta.theme has ID SERIAL
    theme_sql = os.path.join(tables_dir, "meta/theme/create.sql")
    if os.path.exists(theme_sql):
        assert has_serial_column(theme_sql) is True


def test_has_serial_column_without_serial():
    """
    Story: Return False for files without SERIAL

    Given a create.sql file that has no SERIAL column
    When we call has_serial_column
    Then it returns False
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")

    # meta.catalog has no SERIAL columns
    catalog_sql = os.path.join(tables_dir, "meta/catalog/create.sql")
    if os.path.exists(catalog_sql):
        assert has_serial_column(catalog_sql) is False


def test_has_serial_column_nonexistent_file():
    """
    Story: Return False for nonexistent file

    Given a file path that does not exist
    When we call has_serial_column
    Then it returns False
    """
    assert has_serial_column("/nonexistent/path/create.sql") is False


#
# Tests for reset_serial_sequence
#


def test_reset_serial_sequence():
    """
    Story: Reset SERIAL sequence so nextval returns MAX(ID) + 1

    Given a table with a SERIAL column and a row with a high ID
    When we call reset_serial_sequence
    Then the next sequence value is MAX(ID) + 1
    """
    from dev.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    # Create a temp table with SERIAL
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.test_serial_reset (
            "ID" SERIAL PRIMARY KEY,
            "Name" TEXT NOT NULL
        )
        """
    )
    cursor.execute("TRUNCATE meta.test_serial_reset CASCADE")
    conn.commit()

    # Insert a row with specific high ID
    cursor.execute('INSERT INTO meta.test_serial_reset ("ID", "Name") VALUES (100, %s)', ("test",))
    conn.commit()

    # Reset sequence
    reset_serial_sequence("meta.test_serial_reset", cursor)
    conn.commit()

    # Verify nextval returns 101
    cursor.execute('SELECT nextval(\'"meta"."test_serial_reset_ID_seq"\')')
    result = cursor.fetchone()
    assert result["nextval"] == 101

    # Cleanup
    cursor.execute("DROP TABLE IF EXISTS meta.test_serial_reset")
    conn.commit()
    cursor.close()
    conn.close()


def test_reset_serial_sequence_no_id_column():
    """
    Story: Early return when table has no ID column

    Given a table without an ID column
    When we call reset_serial_sequence
    Then it returns without error
    """
    from dev.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    # Create a temp table without an "ID" column
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.test_no_id_col (
            user_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Should return without error (early return path)
    reset_serial_sequence("meta.test_no_id_col", cursor)

    # Cleanup
    cursor.execute("DROP TABLE IF EXISTS meta.test_no_id_col")
    conn.commit()
    cursor.close()
    conn.close()


#
# Tests for seed_catalog_files
#


def test_seed_catalog_files_no_catalogs(temp_tables_dir):
    """
    Story: Return 0 when no catalog.csv files exist

    Given a tables directory with no catalog.csv files
    When we call seed_catalog_files
    Then it returns 0
    """
    # Create empty meta and test dirs (no catalog.csv files)
    (temp_tables_dir / "meta").mkdir()
    (temp_tables_dir / "test").mkdir()
    result = seed_catalog_files(temp_tables_dir)
    assert result == 0


def test_seed_catalog_files_empty_catalog(empty_catalog_file):
    """
    Story: Skip catalog.csv files with no data rows

    Given a catalog.csv file with only a header row
    When we call seed_catalog_files
    Then it returns 0 and skips the empty file
    """
    result = seed_catalog_files(empty_catalog_file)
    assert result == 0


#
# Constants
#

# Use a non-existent schema to avoid modifying real data
TEST_SCHEMA = "etl_test_nonexistent"

#
# Tests for seed_table function
#


def test_seed_table_success():
    """
    Story: Seed table populates tables from CSV files

    Given the database has tables created
    When we call seed_table with isolated schema
    Then it returns success
    """
    data = seed_table(usernames=[TEST_SCHEMA])

    assert data["status"] == "success"
    assert "tables_seeded" in data


def test_seed_table_response_structure():
    """
    Story: Seed table returns proper response structure

    Given a valid request
    When we call seed_table
    Then it returns expected fields
    And the iterations key is not present (DAG replaced retry loop)
    """
    data = seed_table(usernames=[TEST_SCHEMA])

    assert "status" in data
    assert "message" in data
    assert "tables_seeded" in data
    assert "catalogs_seeded" in data
    assert "iterations" not in data


def test_seed_table_with_usernames_filter():
    """
    Story: Seed table can filter by usernames

    Given a request with usernames filter
    When we call seed_table
    Then only tables for those users are seeded
    """
    data = seed_table(usernames=[TEST_SCHEMA])

    assert data["status"] == "success"


def test_seed_table_actually_seeds():
    """
    Story: Seed table successfully imports CSV data into database

    Given the database has tables created for meta schema
    When we call seed_table with meta
    Then tables are populated from seed.csv files
    """
    # Ensure tables exist
    drop_table(schemas=["meta"])
    create_table(usernames=["meta"])

    # Seed the tables
    data = seed_table(usernames=["meta"])

    assert data["status"] == "success"
    assert data["tables_seeded"] > 0


def test_seed_csv_without_create_sql_is_skipped():
    """
    Story: seed.csv files without matching create.sql are skipped

    Given a seed.csv exists without a create.sql
    When we call seed_table
    Then it skips that file and returns success with 0 tables
    """
    # Create a seed.csv in data/tables without create.sql
    project_root = Path(__file__).parent.parent.parent.parent
    tables_dir = project_root / "data" / "tables"
    test_dir = tables_dir / "etl_test_no_create" / "test_table"
    test_dir.mkdir(parents=True, exist_ok=True)
    seed_file = test_dir / "seed.csv"
    seed_file.write_text("col1,col2\na,b\n")

    # Call function - should skip the file without create.sql
    data = seed_table(usernames=["etl_test_no_create"])

    assert data["status"] == "success"
    assert data["tables_seeded"] == 0

    # Cleanup
    seed_file.unlink()
    test_dir.rmdir()
    (tables_dir / "etl_test_no_create").rmdir()


def test_seed_table_dependency_order():
    """
    Story: Tables are seeded in dependency order

    Given meta tables with FK relationships
    When we call seed_table for meta
    Then all tables are seeded successfully (no FK constraint errors)
    """

    # Arrange — ensure tables exist
    drop_table(schemas=["meta"])
    create_table(usernames=["meta"])

    # Act
    data = seed_table(usernames=["meta"])

    # Assert — all tables seeded with no failures
    assert data["status"] == "success"
    assert data["tables_seeded"] > 0
    assert "failed_tables" not in data


def test_seed_table_with_persistent_failure():
    """
    Story: Tables that fail to seed are reported in response

    Given a table where COPY will fail (missing required columns in CSV)
    When we call seed_table
    Then response includes failed_tables count
    """
    from dev.db import get_connection

    # Create a test schema and table with a required column
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE SCHEMA IF NOT EXISTS etl_test_fail")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS etl_test_fail.bad_table (
            "Name" TEXT NOT NULL,
            "Required" TEXT NOT NULL
        )
        """
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Create data files: create.sql matches DB, but seed.csv has wrong column count
    project_root = Path(__file__).parent.parent.parent.parent
    tables_dir = project_root / "data" / "tables"
    test_dir = tables_dir / "etl_test_fail" / "bad_table"
    test_dir.mkdir(parents=True, exist_ok=True)

    create_sql = test_dir / "create.sql"
    create_sql.write_text(
        'CREATE TABLE etl_test_fail.bad_table ("Name" TEXT NOT NULL, "Required" TEXT NOT NULL);'
    )
    seed_csv = test_dir / "seed.csv"
    seed_csv.write_text("Name\ntest_value\n")

    # Call function - should report failure
    data = seed_table(usernames=["etl_test_fail"])

    assert data["status"] == "success"
    assert "failed_tables" in data

    # Cleanup files
    create_sql.unlink()
    seed_csv.unlink()
    test_dir.rmdir()
    (tables_dir / "etl_test_fail").rmdir()

    # Cleanup database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS etl_test_fail.bad_table")
    cursor.execute("DROP SCHEMA IF EXISTS etl_test_fail")
    conn.commit()
    cursor.close()
    conn.close()
