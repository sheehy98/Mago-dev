#
# Imports
#

# Testing
import pytest

# Module under test
from dev.db import execute_query


#
# Tests — execute_query
#


def test_execute_query_empty_string():
    """
    Story: Empty SQL query raises ValueError

    Given an empty string as the SQL query
    When we call execute_query
    Then it raises ValueError before hitting the database
    """

    with pytest.raises(ValueError, match="SQL query cannot be empty"):
        execute_query("")


def test_execute_query_none():
    """
    Story: None SQL query raises ValueError

    Given None as the SQL query
    When we call execute_query
    Then it raises ValueError before hitting the database
    """

    with pytest.raises(ValueError, match="SQL query cannot be empty"):
        execute_query(None)
