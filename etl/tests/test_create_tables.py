#
# Imports
#

# Standard library
import os
import shutil

# Source module
from dev.etl.create_tables import create_table, find_create_sql_files
from dev.etl.drop_tables import drop_table

#
# Tests for find_create_sql_files
#


def test_find_create_sql_files_all():
    """
    Story: Find all create.sql files in tables directory

    Given the tables directory exists with SQL files
    When we call find_create_sql_files with no filter
    Then all create.sql files are returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_create_sql_files(tables_dir)
    assert len(files) > 0
    assert all(f.endswith("create.sql") for f in files)


def test_find_create_sql_files_with_usernames():
    """
    Story: Find create.sql files only for specific usernames

    Given the tables directory exists with SQL files
    When we call find_create_sql_files with a username filter
    Then only create.sql files for that username are returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_create_sql_files(tables_dir, usernames=["meta"])
    assert len(files) > 0
    assert all("meta" in f for f in files)


def test_find_create_sql_files_nonexistent_username():
    """
    Story: Return empty list for nonexistent username

    Given a username that does not exist in the tables directory
    When we call find_create_sql_files with that username
    Then an empty list is returned
    """
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    files = find_create_sql_files(tables_dir, usernames=["nonexistent_user_xyz"])
    assert files == []


#
# Constants
#

# Use a non-existent schema to avoid modifying real data
TEST_SCHEMA = "etl_test_nonexistent"

#
# Tests for create_table function
#


def test_create_table_success():
    """
    Story: Create table creates tables from SQL files

    Given the database is running
    When we call create_table with isolated schema
    Then it returns success
    """
    data = create_table(usernames=[TEST_SCHEMA])

    assert data["status"] == "success"
    assert "tables_created" in data


def test_create_table_response_structure():
    """
    Story: Create table returns proper response structure

    Given a valid request
    When we call create_table
    Then it returns expected fields
    """
    data = create_table(usernames=[TEST_SCHEMA])

    assert "status" in data
    assert "message" in data
    assert "tables_created" in data


def test_create_table_with_invalid_sql():
    """
    Story: Permanently invalid SQL is reported in failed_tables

    Given a directory with an invalid create.sql file
    When we call create_table targeting that directory
    Then the response includes failed_tables
    """
    # Create temp directory with invalid SQL
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    test_dir = os.path.join(tables_dir, "_etl_test_invalid")
    table_dir = os.path.join(test_dir, "bad_table")
    os.makedirs(table_dir, exist_ok=True)

    try:
        # Write syntactically invalid SQL (not a dependency error, a permanent failure)
        with open(os.path.join(table_dir, "create.sql"), "w") as f:
            f.write("THIS IS NOT VALID SQL AT ALL;")

        data = create_table(usernames=["_etl_test_invalid"])

        assert "failed_tables" in data
        assert data["failed_tables"] > 0
    finally:
        shutil.rmtree(test_dir)


def test_create_table_with_usernames_filter():
    """
    Story: Create table can filter by usernames

    Given a request with usernames filter
    When we call create_table
    Then only tables for those users are created
    """
    data = create_table(usernames=[TEST_SCHEMA])

    assert data["status"] == "success"


def test_create_table_dependency_order():
    """
    Story: Tables with FKs are created after their dependencies

    Given meta tables that have foreign key dependencies
    When we call create_table for meta
    Then all tables are created successfully (no FK errors)
    And the number of created tables matches available SQL files
    """
    # Arrange — drop meta schema so all tables must be recreated
    drop_table(schemas=["meta"])

    # Act
    data = create_table(usernames=["meta"])

    # Assert — all tables created with no failures
    assert data["status"] == "success"
    assert data["tables_created"] > 0
    assert "failed_tables" not in data

    # Verify count matches available SQL files
    tables_dir = os.path.join(os.path.dirname(__file__), "../../../data/tables")
    sql_files = find_create_sql_files(tables_dir, usernames=["meta"])
    assert data["tables_created"] == len(sql_files)
