#
# Imports
#

# Standard library
import shutil
from pathlib import Path

# Third party
import pytest

# Paths
import dev.paths as paths

# Environment
from dotenv import load_dotenv
load_dotenv()

#
# Constants
#

# Real tables directory (for copying into tmp_path)
REAL_TABLES_DIR = paths.TABLES_DIR

#
# Helper Functions
#


def redirect_tables(tmp_path: Path) -> Path:
    """Copy real catalogs to tmp_path and swap paths.TABLES_DIR"""
    tables_copy = tmp_path / "tables"
    shutil.copytree(REAL_TABLES_DIR, tables_copy)
    paths.TABLES_DIR = tables_copy
    return tables_copy


def restore_tables():
    """Restore paths.TABLES_DIR to the real directory"""
    paths.TABLES_DIR = REAL_TABLES_DIR


#
# Fixtures
#


@pytest.fixture
def fake_catalog_extra_table(tmp_path):
    """
    Create a temporary catalog.csv with a fake table that doesn't exist in DB.
    This triggers the 'extra_table' validation issue.
    """
    tables_dir = redirect_tables(tmp_path)

    # Add fake table directory with catalog
    temp_dir = tables_dir / "_test_fake_table"
    temp_dir.mkdir(exist_ok=True)

    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "test.fake_nonexistent_table,NULL,0,TABLE,,,,Fake table for testing,\n"
        "test.fake_nonexistent_table,ID,1,SERIAL,FALSE,TRUE,,Fake ID column,1|2|3\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_extra_column(tmp_path):
    """
    Create a temporary catalog.csv documenting a real table with a fake column.
    This triggers the 'extra_column' validation issue.
    """
    tables_dir = redirect_tables(tmp_path)

    # Add fake column directory with catalog
    temp_dir = tables_dir / "_test_extra_column"
    temp_dir.mkdir(exist_ok=True)

    # Use meta.languages which exists - add a fake column
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.languages,Fake_Column_XYZ,99,TEXT,TRUE,FALSE,,This column does not exist,fake\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_type_mismatch(tmp_path):
    """
    Create a temporary catalog.csv with wrong type for an existing column.
    Removes the real catalog from the copy so only our fake one is used.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "languages" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog with wrong type
    temp_dir = tables_dir / "_test_type_mismatch"
    temp_dir.mkdir(exist_ok=True)

    # Document meta.languages.ID with wrong type (should be INTEGER, we say TEXT)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.languages,NULL,0,TABLE,,,,Languages table,\n"
        "meta.languages,ID,1,TEXT,FALSE,TRUE,,Wrong type,1|2|3\n"
        "meta.languages,Name,2,TEXT,FALSE,FALSE,,Language name,English\n"
        "meta.languages,Flag,3,TEXT,FALSE,FALSE,,Emoji flag,\U0001f1fa\U0001f1f8\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_nullability_mismatch(tmp_path):
    """
    Create a temporary catalog.csv with wrong nullability for an existing column.
    Removes the real catalog from the copy so only our fake one is used.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "languages" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog with wrong nullability
    temp_dir = tables_dir / "_test_nullability_mismatch"
    temp_dir.mkdir(exist_ok=True)

    # Document meta.languages.Name with wrong nullable (should be FALSE, we say TRUE)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.languages,NULL,0,TABLE,,,,Languages table,\n"
        "meta.languages,ID,1,INTEGER,FALSE,TRUE,,ID column,1|2|3\n"
        "meta.languages,Name,2,TEXT,TRUE,FALSE,,Wrong nullable,English\n"
        "meta.languages,Flag,3,TEXT,FALSE,FALSE,,Emoji flag,\U0001f1fa\U0001f1f8\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_order_mismatch(tmp_path):
    """
    Create a temporary catalog.csv with wrong order for an existing column.
    Removes the real catalog from the copy so only our fake one is used.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "languages" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog with wrong order
    temp_dir = tables_dir / "_test_order_mismatch"
    temp_dir.mkdir(exist_ok=True)

    # Document meta.languages with wrong column order (ID should be order 1, not 99)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.languages,NULL,0,TABLE,,,,Languages table,\n"
        "meta.languages,ID,99,INTEGER,FALSE,TRUE,,Wrong order,1|2|3\n"
        "meta.languages,Name,2,TEXT,FALSE,FALSE,,Language name,English\n"
        "meta.languages,Flag,3,TEXT,FALSE,FALSE,,Emoji flag,\U0001f1fa\U0001f1f8\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_primary_key_mismatch(tmp_path):
    """
    Create a temporary catalog.csv with wrong primary key setting.
    Removes the real catalog from the copy so only our fake one is used.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "languages" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog with wrong PK
    temp_dir = tables_dir / "_test_pk_mismatch"
    temp_dir.mkdir(exist_ok=True)

    # Document meta.languages.ID with wrong PK (should be TRUE, we say FALSE)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.languages,NULL,0,TABLE,,,,Languages table,\n"
        "meta.languages,ID,1,INTEGER,FALSE,FALSE,,Wrong PK,1|2|3\n"
        "meta.languages,Name,2,TEXT,FALSE,FALSE,,Language name,English\n"
        "meta.languages,Flag,3,TEXT,FALSE,FALSE,,Emoji flag,\U0001f1fa\U0001f1f8\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_fk_missing(tmp_path):
    """
    Create a catalog that documents a column but omits its foreign key.
    This triggers 'foreign_key_missing_in_catalog' when DB has the FK.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "actions" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog without FK on Avatar ID
    temp_dir = tables_dir / "_test_fk_missing"
    temp_dir.mkdir(exist_ok=True)

    # Document meta.actions but omit the FK on Avatar ID (DB has FK to lucide_icon.ID)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.actions,NULL,0,TABLE,,,,Actions table,\n"
        "meta.actions,ID,1,INTEGER,FALSE,TRUE,,ID,1\n"
        "meta.actions,Name,2,TEXT,FALSE,FALSE,,Name,Download\n"
        "meta.actions,Description,3,TEXT,FALSE,FALSE,,Desc,Button\n"
        "meta.actions,Avatar ID,4,INTEGER,TRUE,FALSE,,Missing FK,1\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def fake_catalog_fk_mismatch(tmp_path):
    """
    Create a catalog that documents a different FK than what's in the database.
    This triggers 'foreign_key_mismatch'.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "actions" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog with wrong FK
    temp_dir = tables_dir / "_test_fk_mismatch"
    temp_dir.mkdir(exist_ok=True)

    # Document Avatar ID with wrong FK (DB has lucide_icon.ID, we say languages.ID)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.actions,NULL,0,TABLE,,,,Actions table,\n"
        "meta.actions,ID,1,INTEGER,FALSE,TRUE,,ID,1\n"
        "meta.actions,Name,2,TEXT,FALSE,FALSE,,Name,Download\n"
        "meta.actions,Description,3,TEXT,FALSE,FALSE,,Desc,Button\n"
        "meta.actions,Avatar ID,4,INTEGER,TRUE,FALSE,meta.languages.ID,Wrong FK,1\n"
    )

    yield temp_dir

    restore_tables()


@pytest.fixture
def hidden_catalog_missing_table(tmp_path):
    """
    Remove a table's catalog from the copy to trigger 'missing_table' detection.
    The table will exist in DB but have no catalog entry.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove the catalog from the copy
    real_catalog = tables_dir / "meta" / "languages" / "catalog.csv"
    real_catalog.unlink()

    yield

    restore_tables()


@pytest.fixture
def fake_catalog_missing_column(tmp_path):
    """
    Create a catalog that omits a column that exists in the database.
    This triggers 'missing_column' validation.
    """
    tables_dir = redirect_tables(tmp_path)

    # Remove real catalog from copy
    real_catalog = tables_dir / "meta" / "languages" / "catalog.csv"
    real_catalog.unlink()

    # Add fake catalog without Flag column
    temp_dir = tables_dir / "_test_missing_column"
    temp_dir.mkdir(exist_ok=True)

    # Document meta.languages but omit the 'Flag' column (which exists in DB)
    catalog_file = temp_dir / "catalog.csv"
    catalog_file.write_text(
        "Table,Column,Order,Type,Nullable?,Primary Key?,Foreign Key,Description,Sample Values\n"
        "meta.languages,NULL,0,TABLE,,,,Languages table,\n"
        "meta.languages,ID,1,INTEGER,FALSE,TRUE,,ID,1\n"
        "meta.languages,Name,2,TEXT,FALSE,FALSE,,Name,English\n"
    )

    yield temp_dir

    restore_tables()
