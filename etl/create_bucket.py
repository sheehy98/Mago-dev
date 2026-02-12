#
# Imports
#

# Standard library
import argparse
import json
import logging
import os
from typing import Any

# Storage client
from dev.storage import get_s3_client

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def create_bucket() -> dict[str, Any]:
    """
    Create buckets based on data/buckets directory

    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("create_bucket called")

    # Get buckets directory path
    from dev.paths import BUCKETS_DIR
    buckets_dir = BUCKETS_DIR

    # Get MinIO endpoint
    host = os.getenv("MINIO_EXTERNAL_HOST", "localhost")
    port = os.getenv("MINIO_INTERNAL_PORT", "3462")
    endpoint_url = f"http://{host}:{port}"

    # Create storage client
    client = get_s3_client(endpoint_url=endpoint_url)

    # Get existing buckets
    list_response = client.list_buckets()
    existing_buckets = {bucket["Name"] for bucket in list_response.get("Buckets", [])}

    # Get bucket names from data/buckets directory (exclude .minio)
    bucket_names = [
        item.name for item in buckets_dir.iterdir() if item.is_dir() and item.name != ".minio"
    ]

    # Create each bucket
    buckets_created = []
    buckets_existing = []

    for bucket_name in bucket_names:
        if bucket_name in existing_buckets:
            buckets_existing.append(bucket_name)
            continue

        client.create_bucket(Bucket=bucket_name)
        buckets_created.append(bucket_name)

    logger.info(
        f"create_bucket completed: {len(buckets_created)} created, {len(buckets_existing)} existing"
    )
    return {
        "status": "success",
        "message": f"Created {len(buckets_created)} bucket(s), {len(buckets_existing)} already existed",
        "buckets_created": buckets_created,
        "buckets_existing": buckets_existing,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create MinIO buckets")
    parser.parse_args()
    result = create_bucket()
    print(json.dumps(result, indent=2))
