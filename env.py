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
# Helper Functions
#


def load_env():
    """
    Load environment variables based on MAGO_ENV or -s flag.

    Checks sys.argv for -s/--staging, then MAGO_ENV env var.
    Loads .env or .env.staging files from project root and data/.

    @returns str - The environment that was loaded ("dev" or "staging")
    """

    # Check for -s/--staging flag in sys.argv (before argparse runs)
    if "-s" in sys.argv or "--staging" in sys.argv:
        os.environ["MAGO_ENV"] = "staging"

    # Determine environment
    env = os.getenv("MAGO_ENV", "dev")
    suffix = ".staging" if env == "staging" else ""

    # Load environment files
    # override=True only in staging mode, so test runner env vars are preserved in dev
    load_dotenv(PROJECT_ROOT / f".env{suffix}", override=(env == "staging"))
    load_dotenv(PROJECT_ROOT / "data" / f".env{suffix}", override=(env == "staging"))

    # Staging env uses Docker-internal hostnames (e.g. "postgres", "minio")
    # ETL runs on the host, so override hostnames to localhost
    # and use the host-mapped ports from docker-compose
    if env == "staging":
        os.environ["POSTGRES_HOST"] = "localhost"
        os.environ["MINIO_HOST"] = "localhost"
        os.environ["MINIO_EXTERNAL_HOST"] = "localhost"
        os.environ["MINIO_INTERNAL_PORT"] = os.environ.get("MINIO_PORT", "9000")

    # Print environment info so output always shows which DB is targeted
    db_host = os.getenv("POSTGRES_HOST", "unknown")
    db_port = os.getenv("POSTGRES_PORT", "unknown")
    db_name = os.getenv("POSTGRES_DB", "unknown")
    print(f"[env] {env} mode — {db_name}@{db_host}:{db_port}")

    logger.info("Loaded %s environment", env)
    return env
