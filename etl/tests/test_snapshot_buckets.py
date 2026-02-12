#
# Imports
#

# Standard library
import os

# Third party
import pytest

# Module under test
from dev.etl.drop_bucket import drop_bucket
from dev.etl.snapshot_buckets import snapshot_bucket

# Storage client
from dev.storage import get_s3_client


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets")


#
# Constants
#

# Use isolated test bucket names
TEST_BUCKET = "etl-test-snapshot-bucket"
MINIO_ENDPOINT = f"http://{os.getenv('MINIO_EXTERNAL_HOST', 'localhost')}:{os.getenv('MINIO_INTERNAL_PORT', '3462')}"

#
# Tests for snapshot_bucket function
#


def test_snapshot_bucket_success():
    """
    Story: Snapshot bucket saves bucket contents to filesystem

    Given buckets exist in MinIO
    When we call snapshot_bucket with isolated bucket
    Then bucket contents are saved
    """
    # Create isolated test bucket
    client = get_s3_client(endpoint_url=MINIO_ENDPOINT)
    drop_bucket(buckets=[TEST_BUCKET])
    client.create_bucket(Bucket=TEST_BUCKET)

    # Snapshot only our test bucket
    data = snapshot_bucket(buckets=[TEST_BUCKET])

    assert data["status"] == "success"

    # Cleanup
    drop_bucket(buckets=[TEST_BUCKET])


def test_snapshot_bucket_response_structure():
    """
    Story: Snapshot bucket returns proper response structure

    Given a valid request
    When we call snapshot_bucket
    Then it returns expected fields
    """
    # Create isolated test bucket
    client = get_s3_client(endpoint_url=MINIO_ENDPOINT)
    drop_bucket(buckets=[TEST_BUCKET])
    client.create_bucket(Bucket=TEST_BUCKET)

    data = snapshot_bucket(buckets=[TEST_BUCKET])

    assert "status" in data
    assert "message" in data

    # Cleanup
    drop_bucket(buckets=[TEST_BUCKET])


def test_snapshot_bucket_empty_list():
    """
    Story: Snapshot with empty bucket list returns early

    Given an empty buckets list
    When we call snapshot_bucket
    Then it returns success with empty buckets_snapshotted
    """
    data = snapshot_bucket(buckets=[])

    assert data["status"] == "success"
    assert data["buckets_snapshotted"] == []


def test_snapshot_bucket_full_sync_cycle(redirect_buckets_dir):
    """
    Story: Full sync cycle covers download, re-download, and delete

    Given a bucket with files in MinIO
    When we snapshot, modify local, snapshot again, delete from MinIO, snapshot again
    Then downloads, re-downloads, and deletes are tracked
    """
    client = get_s3_client(endpoint_url=MINIO_ENDPOINT)
    bucket_name = "etl-test-snapshot-sync"
    user_prefix = "etlsyncuser"

    # Filesystem writes go to tmp_path via redirect_buckets_dir
    buckets_dir = redirect_buckets_dir

    try:
        # Setup: create bucket with two files (need two so delete path is exercised)
        drop_bucket(buckets=[bucket_name])
        client.create_bucket(Bucket=bucket_name)
        client.put_object(
            Bucket=bucket_name, Key=f"{user_prefix}/file-a.txt", Body=b"hello world"
        )
        client.put_object(
            Bucket=bucket_name, Key=f"{user_prefix}/file-b.txt", Body=b"keep me"
        )

        # Step 1: First snapshot — downloads both files
        data = snapshot_bucket(buckets=[bucket_name])
        assert data["buckets_snapshotted"][0]["downloaded"] == 2

        # Verify files were downloaded to tmp_path
        local_path_a = buckets_dir / user_prefix / "file-a.txt"
        local_path_b = buckets_dir / user_prefix / "file-b.txt"
        assert local_path_a.exists()
        assert local_path_b.exists()

        # Step 2: Modify local file size to trigger re-download
        local_path_a.write_text("different size content that is much longer than before")

        data = snapshot_bucket(buckets=[bucket_name])
        assert data["buckets_snapshotted"][0]["downloaded"] == 1

        # Step 3: Delete file-a from MinIO (keep file-b so user loop still runs)
        client.delete_object(Bucket=bucket_name, Key=f"{user_prefix}/file-a.txt")

        data = snapshot_bucket(buckets=[bucket_name])
        assert data["buckets_snapshotted"][0]["deleted"] == 1
        assert not local_path_a.exists()

    finally:
        # Cleanup MinIO bucket only — filesystem is tmp_path, cleaned up automatically
        drop_bucket(buckets=[bucket_name])
