#
# Imports
#

# Standard library
import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

# Storage client
from dev.storage import get_s3_client

# Configure logging
logger = logging.getLogger(__name__)

#
# Helper Functions
#


def get_buckets_directory() -> Path:
    """Get the path to the buckets directory"""
    from dev.paths import BUCKETS_DIR
    return BUCKETS_DIR


def save_buckets_file(buckets_dir: Path, usernames: set[str]):
    """Save the .buckets file, merging with existing usernames"""
    buckets_file = buckets_dir / ".buckets"

    # Merge with existing usernames so filtered snapshots don't lose data
    if buckets_file.exists():
        existing = {line.strip() for line in buckets_file.read_text().splitlines() if line.strip()}
        usernames = usernames | existing

    buckets_file.parent.mkdir(parents=True, exist_ok=True)
    with open(buckets_file, "w") as f:
        for username in sorted(usernames):
            f.write(f"{username}\n")


def save_objects_file(directory: Path, filenames: set[str]):
    """Save the .objects file that lists files in a directory"""
    objects_file = directory / ".objects"
    objects_file.parent.mkdir(parents=True, exist_ok=True)
    with open(objects_file, "w") as f:
        for filename in sorted(filenames):
            f.write(f"{filename}\n")


def get_local_files(buckets_dir: Path, username: str) -> set[str]:
    """Get all local files for a user (excluding system files)"""
    user_dir = buckets_dir / username
    if not user_dir.exists():
        return set()

    local_files = set()
    for file_path in user_dir.rglob("*"):
        if file_path.is_file() and file_path.name not in [".objects", ".buckets", ".DS_Store"]:
            relative_path = file_path.relative_to(buckets_dir)
            local_files.add(str(relative_path))
    return local_files


#
# Handler Functions
#


def snapshot_bucket(buckets: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Sync MinIO buckets to local filesystem

    @param buckets (Optional[list[str]]): Specific buckets to snapshot (all if None)
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("snapshot_bucket called")

    # Get paths
    buckets_dir = get_buckets_directory()

    # Get MinIO endpoint
    host = os.getenv("MINIO_EXTERNAL_HOST", "localhost")
    port = os.getenv("MINIO_INTERNAL_PORT", "3462")
    endpoint_url = f"http://{host}:{port}"

    # Create storage client
    client = get_s3_client(endpoint_url=endpoint_url)

    # List all buckets, apply filter if provided (skip non-existent buckets)
    list_response = client.list_buckets()
    existing_buckets = {bucket["Name"] for bucket in list_response.get("Buckets", [])}
    target_buckets = (
        [b for b in buckets if b in existing_buckets]
        if buckets is not None
        else list(existing_buckets)
    )

    if not target_buckets:
        return {"status": "success", "message": "No buckets found", "buckets_snapshotted": []}

    # Track statistics
    total_downloaded = 0
    total_deleted = 0
    buckets_snapshotted = []
    all_usernames = set()

    # Process each bucket
    for bucket_name in target_buckets:
        # List all objects in bucket
        minio_objects = {}
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get("Contents", []):
                minio_objects[obj["Key"]] = obj.get("Size", 0)

        # Group objects by username
        users_objects: dict[str, list[str]] = {}
        for object_key in minio_objects:
            parts = object_key.split("/")
            if parts:
                username = parts[0]
                if username not in users_objects:
                    users_objects[username] = []
                users_objects[username].append(object_key)

        bucket_downloaded = 0
        bucket_deleted = 0

        # Process each user's files
        for username, object_keys in users_objects.items():
            local_files = get_local_files(buckets_dir, username)
            minio_keys = set(object_keys)
            directory_files: dict[Path, set[str]] = {}

            # Download missing or changed files
            for object_key in minio_keys:
                local_path = buckets_dir / object_key
                minio_size = minio_objects[object_key]

                # Track file in directory
                if local_path.parent not in directory_files:
                    directory_files[local_path.parent] = set()
                directory_files[local_path.parent].add(local_path.name)

                # Download if missing or size differs
                should_download = not local_path.exists()
                if local_path.exists() and local_path.stat().st_size != minio_size:
                    should_download = True

                if should_download:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    client.download_file(bucket_name, object_key, str(local_path))
                    bucket_downloaded += 1

            # Update .objects files
            for directory, filenames in directory_files.items():
                save_objects_file(directory, filenames)

            # Delete files not in MinIO
            for object_key in local_files - minio_keys:
                local_path = buckets_dir / object_key
                if local_path.exists():
                    local_path.unlink()
                    bucket_deleted += 1

            all_usernames.add(username)

        total_downloaded += bucket_downloaded
        total_deleted += bucket_deleted
        buckets_snapshotted.append(
            {
                "bucket": bucket_name,
                "downloaded": bucket_downloaded,
                "deleted": bucket_deleted,
            }
        )

    # Update .buckets file (merges with existing so filtered snapshots are safe)
    save_buckets_file(buckets_dir, all_usernames)

    logger.info(
        f"snapshot_bucket completed: {total_downloaded} downloaded, {total_deleted} deleted"
    )
    return {
        "status": "success",
        "message": f"Snapshot: {total_downloaded} downloaded, {total_deleted} deleted",
        "buckets_snapshotted": buckets_snapshotted,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot MinIO buckets")
    parser.add_argument("--buckets", nargs="*", help="Specific buckets to snapshot")
    args = parser.parse_args()
    result = snapshot_bucket(buckets=args.buckets)
    print(json.dumps(result, indent=2))
