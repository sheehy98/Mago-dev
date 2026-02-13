#
# Imports
#

# Standard library
from pathlib import Path

#
# Path Constants
#

# Project root (dev/paths.py → dev → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data directories
TABLES_DIR = PROJECT_ROOT / "data" / "tables"
BUCKETS_DIR = PROJECT_ROOT / "data" / "buckets"
SCHEMA_MMD_PATH = PROJECT_ROOT / "data" / "schema.mmd"

# Frontend source
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
