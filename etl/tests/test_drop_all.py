#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.drop_all import drop_all


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for drop_all function
#


def test_drop_all_success():
    """
    Story: Drop all drops both tables and buckets

    Given the database and MinIO are running
    When we call drop_all
    Then it returns success
    """
    data = drop_all()

    assert data["status"] == "success"
    assert "bucket" in data
    assert "tables" in data


def test_drop_all_response_structure():
    """
    Story: Drop all returns proper response structure

    Given a valid request
    When we call drop_all
    Then it returns expected fields
    """
    data = drop_all()

    assert "status" in data
    assert "message" in data
    assert "bucket" in data
    assert "tables" in data
