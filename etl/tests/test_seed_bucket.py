#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.create_bucket import create_bucket
from dev.etl.seed_bucket import seed_bucket


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for seed_bucket function
#


def test_seed_bucket_empty_list():
    """
    Story: Seeding empty bucket list returns early

    Given an empty buckets list
    When we call seed_bucket
    Then it returns success with no buckets seeded
    """
    data = seed_bucket(buckets=[])

    assert data["status"] == "success"
    assert data["buckets_seeded"] == []


def test_seed_bucket_success():
    """
    Story: Seed bucket uploads files to buckets

    Given buckets exist in MinIO
    When we call seed_bucket
    Then files are uploaded to each bucket
    """
    # Ensure buckets exist
    create_bucket()

    data = seed_bucket()

    assert data["status"] == "success"
    assert "buckets_seeded" in data
    assert "total_files_uploaded" in data


def test_seed_bucket_response_structure():
    """
    Story: Seed bucket returns proper response structure

    Given a valid request
    When we call seed_bucket
    Then it returns expected fields
    """
    data = seed_bucket()

    assert "status" in data
    assert "message" in data
