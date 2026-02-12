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


def seed_bucket(buckets: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Seed MinIO buckets from data/buckets directory

    @param buckets (Optional[list[str]]): Specific buckets to seed (all if None)
    @returns Dict[str, Any] - Response with status and results
    """
    logger.info("seed_bucket called")

    # Get buckets directory path
    from dev.paths import BUCKETS_DIR
    buckets_dir = BUCKETS_DIR

    # Get MinIO endpoint
    host = os.getenv("MINIO_EXTERNAL_HOST", "localhost")
    port = os.getenv("MINIO_INTERNAL_PORT", "3462")
    endpoint_url = f"http://{host}:{port}"

    # Create storage client
    client = get_s3_client(endpoint_url=endpoint_url)

    # List buckets, apply filter if provided (skip non-existent buckets)
    list_response = client.list_buckets()
    existing_buckets = {bucket["Name"] for bucket in list_response.get("Buckets", [])}
    target_buckets = (
        [b for b in buckets if b in existing_buckets]
        if buckets is not None
        else list(existing_buckets)
    )

    if not target_buckets:
        return {"status": "success", "message": "No buckets found to seed", "buckets_seeded": []}

    # Seed each bucket
    buckets_seeded = []
    total_files_uploaded = 0

    for bucket_name in target_buckets:
        uploaded_count = 0

        # Upload files from buckets directory (excluding .minio and .DS_Store)
        for item in buckets_dir.iterdir():
            if item.is_dir() and item.name != ".minio":
                for file_path in item.rglob("*"):
                    if (
                        file_path.is_file()
                        and file_path.name != ".DS_Store"
                        and ".objects" not in file_path.parts
                    ):
                        relative_path = file_path.relative_to(buckets_dir)
                        object_key = str(relative_path).replace("\\", "/")
                        client.upload_file(str(file_path), bucket_name, object_key)
                        uploaded_count += 1

        buckets_seeded.append({"bucket": bucket_name, "files_uploaded": uploaded_count})
        total_files_uploaded += uploaded_count

    logger.info(
        f"seed_bucket completed: {len(buckets_seeded)} buckets seeded, {total_files_uploaded} files uploaded"
    )
    return {
        "status": "success",
        "message": f"Seeded {len(buckets_seeded)} bucket(s) with {total_files_uploaded} total files",
        "buckets_seeded": buckets_seeded,
        "total_files_uploaded": total_files_uploaded,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed MinIO buckets")
    parser.add_argument("--buckets", nargs="*", help="Specific buckets to seed")
    args = parser.parse_args()
    result = seed_bucket(buckets=args.buckets)
    print(json.dumps(result, indent=2))
