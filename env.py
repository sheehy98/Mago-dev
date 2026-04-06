#
# Imports
#

# Standard library
import os
import sys

# Environment variables
from dotenv import load_dotenv

# Local
from dev.paths import PROJECT_ROOT

# Logging
import logging
logger = logging.getLogger(__name__)


#
# Environment Loading
#

#
# Helper Functions
#


def load_env():
    """
    Load environment variables based on MAGO_ENV or -p flag.

    Checks sys.argv for -p/--production, then MAGO_ENV env var.
    Loads .env or .env.production files from project root and data/.

    @returns str - The environment that was loaded ("dev" or "production")
    """

    # Check for -p/--production flag in sys.argv (before argparse runs)
    if "-p" in sys.argv or "--production" in sys.argv:
        os.environ["MAGO_ENV"] = "production"

    # Determine environment
    env = os.getenv("MAGO_ENV", "dev")
    suffix = ".production" if env == "production" else ""

    # Load environment files
    # override=True only in production mode, so test runner env vars are preserved in dev
    load_dotenv(PROJECT_ROOT / f".env{suffix}", override=(env == "production"))
    load_dotenv(PROJECT_ROOT / "data" / f".env{suffix}", override=(env == "production"))

    # Production env uses Docker-internal hostnames (e.g. "postgres", "minio")
    # ETL runs on the host, so override hostnames to localhost
    # and use the host-mapped ports from docker-compose
    if env == "production":
        os.environ["POSTGRES_HOST"] = "localhost"
        os.environ["MINIO_HOST"] = "localhost"
        os.environ["MINIO_EXTERNAL_HOST"] = "localhost"
        os.environ["MINIO_INTERNAL_PORT"] = os.environ.get("MINIO_PORT", "9000")

    # Debug output for troubleshooting
    print(f"[dev.env] MAGO_ENV={env}, MINIO_HOST={os.getenv('MINIO_HOST')}, MINIO_PORT={os.getenv('MINIO_PORT')}")

    logger.info("Loaded %s environment", env)
    return env
