#
# Imports
#

# Standard library
import argparse
import json
import logging
import os
from typing import Any, Optional

# Storage client
from dev.storage import get_s3_client

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def drop_bucket(buckets: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Drop MinIO buckets

    @param buckets (Optional[list[str]]): Specific buckets to drop (all if None)
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("drop_bucket called")

    # Get MinIO endpoint
    host = os.getenv("MINIO_EXTERNAL_HOST", "localhost")
    port = os.getenv("MINIO_INTERNAL_PORT", "3462")
    endpoint_url = f"http://{host}:{port}"

    # Create storage client
    client = get_s3_client(endpoint_url=endpoint_url)

    # Get existing buckets (single call instead of two)
    list_response = client.list_buckets()
    existing_buckets = {bucket["Name"] for bucket in list_response.get("Buckets", [])}

    # Get buckets to drop
    target_buckets = buckets if buckets is not None else list(existing_buckets)

    if not target_buckets:
        return {"status": "success", "message": "No buckets to drop", "buckets_dropped": 0}

    # Drop each bucket
    dropped_count = 0
    for bucket_name in target_buckets:
        if bucket_name not in existing_buckets:
            continue

        # Delete all objects first
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get("Contents", []):
                client.delete_object(Bucket=bucket_name, Key=obj["Key"])

        # Delete the bucket
        client.delete_bucket(Bucket=bucket_name)
        dropped_count += 1

    logger.info(f"drop_bucket completed: {dropped_count} buckets dropped")
    return {
        "status": "success",
        "message": f"Dropped {dropped_count} bucket(s)",
        "buckets_dropped": dropped_count,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop MinIO buckets")
    parser.add_argument("--buckets", nargs="*", help="Specific buckets to drop")
    args = parser.parse_args()
    result = drop_bucket(buckets=args.buckets)
    print(json.dumps(result, indent=2))
