#
# Imports
#

# Standard library
import os

# AWS SDK
import boto3
from botocore.config import Config

# Environment variables
from dotenv import load_dotenv
load_dotenv()

# Logging
import logging
logger = logging.getLogger(__name__)


#
# Constants
#

# MinIO configuration
MINIO_HOST = os.getenv("MINIO_HOST")
MINIO_PORT = os.getenv("MINIO_PORT")
MINIO_ENDPOINT = f"http://{MINIO_HOST}:{MINIO_PORT}" if MINIO_HOST and MINIO_PORT else None
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
MINIO_REGION = os.getenv("MINIO_REGION")


#
# Helper Functions
#


def get_s3_client(endpoint_url: str | None = None):
    """
    Create a configured boto3 S3 client for MinIO.

    @param endpoint_url (str | None): Optional endpoint URL override
    @returns boto3 S3 client
    """

    # Use provided endpoint or fall back to environment
    endpoint = endpoint_url or MINIO_ENDPOINT

    # Configure for MinIO (path-style addressing)
    config = Config(
        region_name=MINIO_REGION, signature_version="s3v4", s3={"addressing_style": "path"}
    )

    logger.debug("Creating S3 client (endpoint=%s)", endpoint)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=config,
    )
