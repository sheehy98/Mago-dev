#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.seed_all import seed_all


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for seed_all function
#


def test_seed_all_success():
    """
    Story: Seed all seeds both tables and buckets

    Given the database and MinIO are running with tables/buckets created
    When we call seed_all
    Then it returns success
    """
    data = seed_all()

    assert data["status"] == "success"
    assert "bucket" in data
    assert "tables" in data


def test_seed_all_response_structure():
    """
    Story: Seed all returns proper response structure

    Given a valid request
    When we call seed_all
    Then it returns expected fields
    """
    data = seed_all()

    assert "status" in data
    assert "message" in data
    assert "bucket" in data
    assert "tables" in data
