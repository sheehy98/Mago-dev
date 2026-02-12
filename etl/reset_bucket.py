#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers for bucket operations
from .drop_bucket import drop_bucket
from .seed_bucket import seed_bucket

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def reset_bucket() -> dict[str, Any]:
    """
    Reset buckets (drop and seed all buckets)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("reset_bucket called")

    # Drop all buckets
    drop_result = drop_bucket()

    # Seed all buckets
    seed_result = seed_bucket()

    logger.info("reset_bucket completed successfully")
    return {
        "status": "success",
        "message": "Buckets reset successfully",
        "drop": drop_result,
        "seed": seed_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset buckets")
    parser.parse_args()
    result = reset_bucket()
    print(json.dumps(result, indent=2))
