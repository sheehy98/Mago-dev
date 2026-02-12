#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers
from .drop_bucket import drop_bucket
from .drop_tables import drop_table

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def drop_all() -> dict[str, Any]:
    """
    Drop all resources (tables and bucket)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("drop_all called")

    # Drop tables first, then buckets
    tables_result = drop_table()
    bucket_result = drop_bucket()

    logger.info("drop_all completed successfully")
    return {
        "status": "success",
        "message": "Bucket and tables dropped successfully",
        "bucket": bucket_result,
        "tables": tables_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop all resources")
    parser.parse_args()
    result = drop_all()
    print(json.dumps(result, indent=2))
