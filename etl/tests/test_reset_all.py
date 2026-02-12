#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.reset_all import reset_all


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for reset_all function
#


def test_reset_all_success():
    """
    Story: Reset all drops, creates, and seeds everything

    Given the database and MinIO are running
    When we call reset_all
    Then it returns success
    """
    data = reset_all()

    assert data["status"] == "success"
    assert "drop" in data
    assert "create" in data
    assert "seed" in data


def test_reset_all_response_structure():
    """
    Story: Reset all returns proper response structure

    Given a valid request
    When we call reset_all
    Then it returns expected fields
    """
    data = reset_all()

    assert "status" in data
    assert "message" in data
    assert "drop" in data
    assert "create" in data
    assert "seed" in data
