#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers
from .seed_bucket import seed_bucket
from .seed_tables import seed_table

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def seed_all() -> dict[str, Any]:
    """
    Seed all resources (bucket and tables)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("seed_all called")

    # Seed buckets and tables
    bucket_result = seed_bucket()
    tables_result = seed_table()

    logger.info("seed_all completed successfully")
    return {
        "status": "success",
        "message": "Bucket and tables seeded successfully",
        "bucket": bucket_result,
        "tables": tables_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed all resources")
    parser.parse_args()
    result = seed_all()
    print(json.dumps(result, indent=2))
