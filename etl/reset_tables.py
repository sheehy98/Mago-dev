#
# Imports
#

# Standard library
import argparse
import json
import logging
from typing import Any

# Import handlers
from .create_tables import create_table
from .drop_tables import drop_table
from .seed_tables import seed_table

# Configure logging
logger = logging.getLogger(__name__)

#
# Handler Functions
#


def reset_table() -> dict[str, Any]:
    """
    Reset tables (drop, create, and seed)

    @returns Dict[str, Any] - Response with status and results
    """

    logger.info("reset_table called")

    # Drop, create, and seed tables
    drop_result = drop_table()
    create_result = create_table()
    seed_result = seed_table()

    logger.info("reset_table completed successfully")
    return {
        "status": "success",
        "message": "Tables reset successfully",
        "drop": drop_result,
        "create": create_result,
        "seed": seed_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset tables")
    parser.parse_args()
    result = reset_table()
    print(json.dumps(result, indent=2))
