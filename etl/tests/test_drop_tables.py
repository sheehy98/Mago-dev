#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.drop_tables import drop_table, quote_identifier
from dev.etl.reset_tables import reset_table

#
# Fixtures
#


@pytest.fixture(autouse=True)
def recreate_tables_after_drop():
    """Recreate tables after each drop test to avoid breaking subsequent tests"""
    yield
    # After each test, fully reset the database (drop + create + seed handles FK order)
    reset_table()


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
    assert quote_identifier('"schema.table"') == '"schema.table"'


def test_quote_identifier_needs_quoting_uppercase():
    """
    Story: Identifiers with uppercase need quoting

    Given an identifier containing uppercase letters
    When we call quote_identifier
    Then the identifier is wrapped in double quotes
    """
    assert quote_identifier("MyTable") == '"MyTable"'
    assert quote_identifier("myTable") == '"myTable"'
    assert quote_identifier("USERS") == '"USERS"'


def test_quote_identifier_needs_quoting_starts_with_digit():
    """
    Story: Identifiers starting with digit need quoting

    Given an identifier that starts with a digit
    When we call quote_identifier
    Then the identifier is wrapped in double quotes
    """
    assert quote_identifier("1table") == '"1table"'
    assert quote_identifier("123") == '"123"'


def test_quote_identifier_needs_quoting_special_chars():
    """
    Story: Identifiers with special characters need quoting

    Given an identifier containing special characters like hyphens, dots, or spaces
    When we call quote_identifier
    Then the identifier is wrapped in double quotes
    """
    assert quote_identifier("my-table") == '"my-table"'
    assert quote_identifier("my.table") == '"my.table"'
    assert quote_identifier("my table") == '"my table"'


def test_quote_identifier_no_quoting_needed():
    """
    Story: Simple lowercase identifiers don't need quoting

    Given an identifier with only lowercase letters, digits, and underscores
    When we call quote_identifier
    Then the identifier is returned without quotes
    """
    assert quote_identifier("users") == "users"
    assert quote_identifier("my_table") == "my_table"
    assert quote_identifier("test123") == "test123"


#
# Tests for drop_table function
#


def test_drop_tables_with_empty_schemas_list():
    """
    Story: Dropping with empty schemas list drops all schemas from data/tables

    Given an empty schemas list
    When we call drop_tables
    Then it derives schemas from data/tables directory and drops them all
    """
    data = drop_table(schemas=[])

    assert data["status"] == "success"
    # Empty list means "drop all from data/tables"
    assert data["schemas_dropped"] >= 1


def test_drop_tables_with_nonexistent_schema():
    """
    Story: Dropping nonexistent schema succeeds (IF EXISTS)

    Given a schema that doesn't exist
    When we call drop_tables
    Then it returns success (DROP IF EXISTS doesn't error)
    """
    data = drop_table(schemas=["_nonexistent_schema_xyz_12345"])

    assert data["status"] == "success"
    assert data["schemas_dropped"] == 1


def test_drop_tables_no_schemas_specified():
    """
    Story: Empty body drops all schemas from data/tables

    Given a request with no schemas or usernames specified
    When we call drop_table
    Then it derives schemas from data/tables directory and drops them all
    """
    data = drop_table()

    assert data["status"] == "success"
    # No schemas specified means "drop all from data/tables"
    assert data["schemas_dropped"] >= 1


def test_drop_tables_response_structure():
    """
    Story: Endpoint returns proper response structure

    Given a valid request
    When we call drop_tables
    Then it returns expected fields
    """
    data = drop_table(schemas=["_nonexistent_test_schema_"])

    # Verify response structure
    assert "status" in data
    assert "message" in data
    assert "schemas_dropped" in data
