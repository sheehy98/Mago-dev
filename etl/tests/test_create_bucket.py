#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.create_bucket import create_bucket
from dev.etl.drop_bucket import drop_bucket


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Tests for create_bucket function
#
# Note: create_bucket creates buckets based on data/buckets directory
# It does not accept a filter parameter.
#


def test_create_bucket_success():
    """
    Story: Create bucket creates buckets from data/buckets directory

    Given the MinIO storage is running
    When we call create_bucket
    Then buckets are created or reported as existing
    """
    data = create_bucket()

    assert data["status"] == "success"
    assert "buckets_created" in data
    assert "buckets_existing" in data


def test_create_bucket_response_structure():
    """
    Story: Create bucket returns proper response structure

    Given a valid request
    When we call create_bucket
    Then it returns expected fields
    """
    data = create_bucket()

    assert "status" in data
    assert "message" in data


def test_create_bucket_creates_missing_bucket():
    """
    Story: Create bucket creates a bucket that was dropped

    Given a known bucket (meta) has been dropped
    When we call create_bucket
    Then that bucket appears in buckets_created
    """
    # Drop the meta bucket
    drop_bucket(buckets=["meta"])

    # Recreate — meta should be in buckets_created
    data = create_bucket()

    assert "meta" in data["buckets_created"]


def test_create_bucket_idempotent():
    """
    Story: Create bucket is idempotent

    Given buckets already exist
    When we call create_bucket again
    Then existing buckets are reported, not re-created
    """
    # First call ensures buckets are created
    create_bucket()

    # Second call should report all as existing
    data = create_bucket()

    assert data["status"] == "success"
    # On second call, buckets should be existing, not created
    assert data["buckets_created"] == []
