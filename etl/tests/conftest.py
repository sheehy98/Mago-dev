#
# Imports
#

# Standard library
import os

# Third party
import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

# ETL functions
from dev.etl.create_bucket import create_bucket
from dev.etl.drop_bucket import drop_bucket
from dev.etl.reset_all import reset_all
from dev.etl.seed_bucket import seed_bucket

# Environment variables
from dotenv import load_dotenv
load_dotenv()


#
# RollbackConnection
#


class RollbackConnection:
    """
    Wraps a real psycopg2 connection for transaction rollback in tests.

    Intercepts commit() and close() to keep all operations within a single
    transaction. Uses savepoints so that query failures don't poison the
    entire transaction — ROLLBACK TO SAVEPOINT recovers the error state.

    Key invariant: after cursor() or commit(), there is always an active
    savepoint protecting subsequent operations from poisoning the transaction.
    """

    def __init__(self, real_conn):
        self._conn = real_conn
        self._sp_counter = 0
        self._active_sp = None

    def _run(self, sql):
        """Execute a management SQL statement on the real connection"""
        c = self._conn.cursor()
        c.execute(sql)
        c.close()

    def _release_savepoint(self):
        """Release the active savepoint, recovering from errors if needed"""
        if self._active_sp is None:
            return
        try:
            self._run(f"RELEASE SAVEPOINT {self._active_sp}")
        except Exception:
            # Transaction in error state — rollback to savepoint first
            self._run(f"ROLLBACK TO SAVEPOINT {self._active_sp}")
        self._active_sp = None

    def _create_savepoint(self):
        """Create a new savepoint"""
        self._sp_counter += 1
        self._active_sp = f"sp_{self._sp_counter}"
        self._run(f"SAVEPOINT {self._active_sp}")

    def cursor(self, *args, **kwargs):
        """Clean up previous savepoint, create a new one, return real cursor"""
        self._release_savepoint()
        self._create_savepoint()
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        """Release savepoint (persisting changes in transaction) and create a new one"""
        self._release_savepoint()
        self._create_savepoint()

    def close(self):
        """Roll back to active savepoint and release it (undo uncommitted work)"""
        self._release_savepoint()


#
# Fixtures
#


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Seed database and buckets once at the start of the test session"""
    reset_all()


@pytest.fixture(autouse=True)
def db_rollback():
    """Wrap each test in a DB transaction that gets rolled back after"""

    # Save original connect function
    original_connect = psycopg2.connect

    # Create real connection before patching
    real_conn = original_connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        cursor_factory=RealDictCursor,
    )

    # Patch psycopg2.connect to return our rollback wrapper
    wrapper = RollbackConnection(real_conn)
    psycopg2.connect = lambda *args, **kwargs: wrapper

    yield

    # Rollback all DB changes and close
    real_conn.rollback()
    real_conn.close()

    # Restore original connect
    psycopg2.connect = original_connect


@pytest.fixture
def restore_buckets():
    """Restore MinIO buckets to seeded state after test"""
    yield
    drop_bucket()
    create_bucket()
    seed_bucket()


@pytest.fixture
def redirect_tables_dir(tmp_path):
    """Swap paths.TABLES_DIR to a tmp_path directory, restore after test"""
    import dev.paths as paths
    original = paths.TABLES_DIR
    paths.TABLES_DIR = tmp_path
    yield tmp_path
    paths.TABLES_DIR = original


@pytest.fixture
def redirect_buckets_dir(tmp_path):
    """Swap paths.BUCKETS_DIR to a tmp_path directory, restore after test"""
    import dev.paths as paths
    original = paths.BUCKETS_DIR
    paths.BUCKETS_DIR = tmp_path
    yield tmp_path
    paths.BUCKETS_DIR = original


@pytest.fixture
def redirect_all_paths(tmp_path):
    """Swap all filesystem paths to tmp_path, pre-populate with real data/tables copy"""
    import shutil

    import dev.paths as paths

    # Save originals
    orig_tables = paths.TABLES_DIR
    orig_buckets = paths.BUCKETS_DIR
    orig_mmd = paths.SCHEMA_MMD_PATH

    # Copy real tables to tmp_path
    shutil.copytree(orig_tables, tmp_path / "tables")
    if orig_mmd.exists():
        shutil.copy2(orig_mmd, tmp_path / "schema.mmd")

    # Swap paths
    paths.TABLES_DIR = tmp_path / "tables"
    paths.BUCKETS_DIR = tmp_path / "buckets"
    paths.SCHEMA_MMD_PATH = tmp_path / "schema.mmd"

    yield tmp_path

    # Restore
    paths.TABLES_DIR = orig_tables
    paths.BUCKETS_DIR = orig_buckets
    paths.SCHEMA_MMD_PATH = orig_mmd


@pytest.fixture
def temp_tables_dir(tmp_path):
    """Create a temporary tables directory structure"""
    return tmp_path


@pytest.fixture
def empty_catalog_file(tmp_path):
    """Create a catalog.csv with only a header (no data rows)"""
    meta_dir = tmp_path / "meta" / "empty_table"
    meta_dir.mkdir(parents=True)
    catalog_file = meta_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
    )
    return tmp_path
