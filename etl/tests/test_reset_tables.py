#
# Imports
#

# Module under test
from dev.etl.reset_tables import reset_table

#
# Tests for reset_table function
#


def test_reset_table_success():
    """
    Story: Reset table drops, creates, and seeds tables

    Given the database is running
    When we call reset_table
    Then it returns success
    """
    data = reset_table()

    assert data["status"] == "success"
    assert "drop" in data
    assert "create" in data
    assert "seed" in data


def test_reset_table_response_structure():
    """
    Story: Reset table returns proper response structure

    Given a valid request
    When we call reset_table
    Then it returns expected fields
    """
    data = reset_table()

    assert "status" in data
    assert "message" in data
    assert "drop" in data
    assert "create" in data
    assert "seed" in data
