#
# Imports
#

# Standard library
import os

# Third party
import pytest

# Source module
from dev.etl.drop_bucket import drop_bucket
from dev.storage import get_s3_client


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Constants
#

# MinIO endpoint (port set by run_tests.sh via env var)
MINIO_ENDPOINT = f"http://{os.getenv('MINIO_EXTERNAL_HOST', 'localhost')}:{os.getenv('MINIO_INTERNAL_PORT', '3462')}"

#
# Tests for drop_bucket function
#


def test_drop_bucket_with_empty_list():
    """
    Story: Dropping empty buckets list returns success

    Given an empty buckets list
    When we call drop_bucket
    Then it returns success with 0 buckets dropped
    """
    data = drop_bucket(buckets=[])

    assert data["status"] == "success"
    assert data["buckets_dropped"] == 0


def test_drop_bucket_response_structure():
    """
    Story: Endpoint returns proper response structure

    Given a valid request
    When we call drop_bucket
    Then it returns expected fields
    """
    data = drop_bucket(buckets=[])

    assert "status" in data
    assert "message" in data
    assert "buckets_dropped" in data


def test_drop_bucket_nonexistent():
    """
    Story: Dropping nonexistent bucket returns success with 0 dropped

    Given a bucket that doesn't exist
    When we call drop_bucket with that bucket name
    Then it returns success with 0 buckets dropped (like DROP IF EXISTS)
    """
    bucket_name = "nonexistent-bucket-xyz-12345"

    data = drop_bucket(buckets=[bucket_name])

    assert data["status"] == "success"
    assert data["buckets_dropped"] == 0


def test_drop_bucket_actual_bucket():
    """
    Story: Create a bucket directly and drop it via function

    Given a bucket created via storage client
    When we call drop_bucket with that bucket name
    Then the bucket is deleted
    """
    bucket_name = "test-drop-temp-xyz"

    # Create the bucket directly via storage client (drop first to ensure clean state)
    client = get_s3_client(endpoint_url=MINIO_ENDPOINT)
    drop_bucket(buckets=[bucket_name])
    client.create_bucket(Bucket=bucket_name)

    # Verify bucket exists
    list_response = client.list_buckets()
    bucket_names = [b["Name"] for b in list_response.get("Buckets", [])]
    assert bucket_name in bucket_names

    # Drop it via function
    data = drop_bucket(buckets=[bucket_name])

    assert data["status"] == "success"
    assert data["buckets_dropped"] == 1

    # Verify bucket no longer exists
    list_response = client.list_buckets()
    bucket_names = [b["Name"] for b in list_response.get("Buckets", [])]
    assert bucket_name not in bucket_names


def test_drop_bucket_with_contents():
    """
    Story: Drop a bucket that contains objects

    Given a bucket with objects in it
    When we call drop_bucket
    Then objects are deleted first, then the bucket
    """
    bucket_name = "test-drop-with-contents"

    # Create bucket and add an object (drop first to ensure clean state)
    client = get_s3_client(endpoint_url=MINIO_ENDPOINT)
    drop_bucket(buckets=[bucket_name])
    client.create_bucket(Bucket=bucket_name)
    client.put_object(Bucket=bucket_name, Key="test-file.txt", Body=b"test content")

    # Drop it via function
    data = drop_bucket(buckets=[bucket_name])

    assert data["status"] == "success"
    assert data["buckets_dropped"] == 1

    # Verify bucket no longer exists
    list_response = client.list_buckets()
    bucket_names = [b["Name"] for b in list_response.get("Buckets", [])]
    assert bucket_name not in bucket_names


def test_drop_multiple_buckets():
    """
    Story: Drop multiple buckets at once

    Given multiple test buckets exist in MinIO
    When we call drop_bucket with those bucket names
    Then all specified buckets are dropped
    """
    # Create test buckets (drop first to ensure clean state)
    client = get_s3_client(endpoint_url=MINIO_ENDPOINT)
    test_buckets = ["test-drop-multi-a", "test-drop-multi-b"]
    drop_bucket(buckets=test_buckets)
    for bucket in test_buckets:
        client.create_bucket(Bucket=bucket)

    # Drop only our test buckets (not all buckets!)
    data = drop_bucket(buckets=test_buckets)

    assert data["status"] == "success"
    assert data["buckets_dropped"] == 2

    # Verify test buckets no longer exist
    list_response = client.list_buckets()
    bucket_names = [b["Name"] for b in list_response.get("Buckets", [])]
    for bucket in test_buckets:
        assert bucket not in bucket_names
