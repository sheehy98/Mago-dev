#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers
from .create_bucket import create_bucket
from .create_tables import create_table

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def create_all() -> dict[str, Any]:
    """
    Create all resources (bucket and tables)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("create_all called")

    # Create buckets and tables
    bucket_result = create_bucket()
    tables_result = create_table()

    logger.info("create_all completed successfully")
    return {
        "status": "success",
        "message": "Bucket and tables created successfully",
        "bucket": bucket_result,
        "tables": tables_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create all resources")
    parser.parse_args()
    result = create_all()
    print(json.dumps(result, indent=2))
