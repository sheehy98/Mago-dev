#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.reset_bucket import reset_bucket


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for reset_bucket function
#


def test_reset_bucket_success():
    """
    Story: Reset bucket drops and seeds buckets

    Given the MinIO storage is running
    When we call reset_bucket
    Then it returns success
    """
    data = reset_bucket()

    assert data["status"] == "success"
    assert "drop" in data
    assert "seed" in data


def test_reset_bucket_response_structure():
    """
    Story: Reset bucket returns proper response structure

    Given a valid request
    When we call reset_bucket
    Then it returns expected fields
    """
    data = reset_bucket()

    assert "status" in data
    assert "message" in data
    assert "drop" in data
    assert "seed" in data
