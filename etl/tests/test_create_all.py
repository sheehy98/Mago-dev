#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.create_all import create_all


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for create_all function
#


def test_create_all_success():
    """
    Story: Create all creates both tables and buckets

    Given the database and MinIO are running
    When we call create_all
    Then it returns success
    """
    data = create_all()

    assert data["status"] == "success"
    assert "bucket" in data
    assert "tables" in data


def test_create_all_response_structure():
    """
    Story: Create all returns proper response structure

    Given a valid request
    When we call create_all
    Then it returns expected fields
    """
    data = create_all()

    assert "status" in data
    assert "message" in data
    assert "bucket" in data
    assert "tables" in data
