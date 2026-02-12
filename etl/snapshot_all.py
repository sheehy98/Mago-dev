#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers
from .snapshot_buckets import snapshot_bucket
from .snapshot_tables import snapshot_table

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def snapshot_all() -> dict[str, Any]:
    """
    Snapshot all resources (tables and bucket)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("snapshot_all called")

    # Snapshot tables and buckets
    tables_result = snapshot_table()
    bucket_result = snapshot_bucket()

    logger.info("snapshot_all completed successfully")
    return {
        "status": "success",
        "message": "Bucket and tables snapshotted successfully",
        "tables": tables_result,
        "bucket": bucket_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot all resources")
    parser.parse_args()
    result = snapshot_all()
    print(json.dumps(result, indent=2))
