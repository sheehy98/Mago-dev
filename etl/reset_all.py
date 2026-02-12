#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers
from .create_all import create_all
from .drop_all import drop_all
from .seed_all import seed_all

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def reset_all() -> dict[str, Any]:
    """
    Reset all resources (drop, create, and seed)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("reset_all called")

    # Drop, create, and seed all
    drop_result = drop_all()
    create_result = create_all()
    seed_result = seed_all()

    logger.info("reset_all completed successfully")
    return {
        "status": "success",
        "message": "Bucket and tables reset successfully",
        "drop": drop_result,
        "create": create_result,
        "seed": seed_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset all resources")
    parser.parse_args()
    result = reset_all()
    print(json.dumps(result, indent=2))
