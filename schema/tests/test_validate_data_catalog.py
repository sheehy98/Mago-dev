#
# Imports
#

# Module under test
from dev.schema.validate_data_catalog import validate_data_catalog

#
# Tests
#


def test_validate_data_catalog_success():
    """
    Story: Validate the data catalog against the database schema

    Given the database has tables in meta and test schemas
    And catalog.csv files exist documenting those tables
    When we call the validate_data_catalog endpoint
    Then it returns validation results with no issues
    """
    data = validate_data_catalog()

    # Verify response structure
    assert "status" in data
    assert "valid" in data
    assert "message" in data
    assert "issues" in data
    assert "total_issues" in data
    assert "tables_checked" in data
    assert "total_db_tables" in data
    assert "total_catalog_tables" in data

    # Status should be either success or validation_errors
    assert data["status"] in ["success", "validation_errors"]

    # valid should match whether there are issues
    assert data["valid"] == (data["total_issues"] == 0)

    # Issues should be a list
    assert isinstance(data["issues"], list)

    # total_issues should match issues length
    assert data["total_issues"] == len(data["issues"])

    # Should have checked some tables
    assert data["total_db_tables"] > 0
    assert data["total_catalog_tables"] > 0


def test_validate_detects_extra_table(fake_catalog_extra_table):
    """
    Story: Detect tables documented in catalog but missing from database

    Given a catalog.csv documents a table that doesn't exist
    When we validate
    Then it reports an extra_table issue
    """
    data = validate_data_catalog()

    # Find the extra_table issue for our fake table
    extra_table_issues = [
        i
        for i in data["issues"]
        if i["type"] == "extra_table" and "fake_nonexistent_table" in i["table"]
    ]

    assert len(extra_table_issues) == 1
    assert "does not exist in database" in extra_table_issues[0]["message"]


def test_validate_detects_extra_column(fake_catalog_extra_column):
    """
    Story: Detect columns documented in catalog but missing from database

    Given a catalog.csv documents a column that doesn't exist
    When we validate
    Then it reports an extra_column issue
    """
    data = validate_data_catalog()

    # Find the extra_column issue for our fake column
    extra_column_issues = [
        i
        for i in data["issues"]
        if i["type"] == "extra_column" and i.get("column") == "Fake_Column_XYZ"
    ]

    assert len(extra_column_issues) == 1
    assert "does not exist in database" in extra_column_issues[0]["message"]


def test_validate_detects_order_mismatch(fake_catalog_order_mismatch):
    """
    Story: Detect order mismatches between database and catalog

    Given a catalog.csv documents a column with the wrong order
    When we validate
    Then it reports an order_mismatch issue
    """
    data = validate_data_catalog()

    # Find the order_mismatch issue
    order_mismatch_issues = [
        i
        for i in data["issues"]
        if i["type"] == "order_mismatch"
        and i.get("table") == "meta.languages"
        and i.get("column") == "ID"
    ]

    assert len(order_mismatch_issues) == 1
    assert "Order mismatch" in order_mismatch_issues[0]["message"]


def test_validate_detects_type_mismatch(fake_catalog_type_mismatch):
    """
    Story: Detect type mismatches between database and catalog

    Given a catalog.csv documents a column with the wrong type
    When we validate
    Then it reports a type_mismatch issue
    """
    data = validate_data_catalog()

    # Find the type_mismatch issue
    type_mismatch_issues = [
        i
        for i in data["issues"]
        if i["type"] == "type_mismatch"
        and i.get("table") == "meta.languages"
        and i.get("column") == "ID"
    ]

    assert len(type_mismatch_issues) == 1
    assert "Type mismatch" in type_mismatch_issues[0]["message"]


def test_validate_detects_nullability_mismatch(fake_catalog_nullability_mismatch):
    """
    Story: Detect nullability mismatches between database and catalog

    Given a catalog.csv documents a column with wrong nullable setting
    When we validate
    Then it reports a nullability_mismatch issue
    """
    data = validate_data_catalog()

    # Find the nullability_mismatch issue
    nullability_mismatch_issues = [
        i
        for i in data["issues"]
        if i["type"] == "nullability_mismatch"
        and i.get("table") == "meta.languages"
        and i.get("column") == "Name"
    ]

    assert len(nullability_mismatch_issues) == 1
    assert "Nullability mismatch" in nullability_mismatch_issues[0]["message"]


def test_validate_detects_primary_key_mismatch(fake_catalog_primary_key_mismatch):
    """
    Story: Detect primary key mismatches between database and catalog

    Given a catalog.csv documents a column with wrong primary key setting
    When we validate
    Then it reports a primary_key_mismatch issue
    """
    data = validate_data_catalog()

    # Find the primary_key_mismatch issue
    pk_mismatch_issues = [
        i
        for i in data["issues"]
        if i["type"] == "primary_key_mismatch"
        and i.get("table") == "meta.languages"
        and i.get("column") == "ID"
    ]

    assert len(pk_mismatch_issues) == 1
    assert "Primary key mismatch" in pk_mismatch_issues[0]["message"]


def test_validate_detects_fk_missing_in_catalog(fake_catalog_fk_missing):
    """
    Story: Detect foreign keys in DB that aren't documented in catalog

    Given a column has a FK in the database
    But the catalog doesn't document that FK
    When we validate
    Then it reports a foreign_key_missing_in_catalog issue
    """
    data = validate_data_catalog()

    # Find the foreign_key_missing_in_catalog issue
    fk_missing_issues = [
        i
        for i in data["issues"]
        if i["type"] == "foreign_key_missing_in_catalog"
        and i.get("table") == "meta.actions"
        and i.get("column") == "Avatar ID"
    ]

    assert len(fk_missing_issues) == 1
    assert "not documented in catalog" in fk_missing_issues[0]["message"]


def test_validate_detects_fk_mismatch(fake_catalog_fk_mismatch):
    """
    Story: Detect foreign key mismatches between database and catalog

    Given a column has a FK in the database
    And the catalog documents a different FK
    When we validate
    Then it reports a foreign_key_mismatch issue
    """
    data = validate_data_catalog()

    # Find the foreign_key_mismatch issue
    fk_mismatch_issues = [
        i
        for i in data["issues"]
        if i["type"] == "foreign_key_mismatch"
        and i.get("table") == "meta.actions"
        and i.get("column") == "Avatar ID"
    ]

    assert len(fk_mismatch_issues) == 1
    assert "Foreign key mismatch" in fk_mismatch_issues[0]["message"]


def test_validate_detects_missing_table(hidden_catalog_missing_table):
    """
    Story: Detect tables in DB that aren't documented in catalog

    Given a table exists in the database
    But no catalog.csv documents that table
    When we validate
    Then it reports a missing_table issue
    """
    data = validate_data_catalog()

    # Find the missing_table issue for meta.languages
    missing_table_issues = [
        i
        for i in data["issues"]
        if i["type"] == "missing_table" and i.get("table") == "meta.languages"
    ]

    assert len(missing_table_issues) == 1
    assert "not documented in catalog" in missing_table_issues[0]["message"]


def test_validate_detects_missing_column(fake_catalog_missing_column):
    """
    Story: Detect columns in DB that aren't documented in catalog

    Given a column exists in the database
    But the catalog doesn't document that column
    When we validate
    Then it reports a missing_column issue
    """
    data = validate_data_catalog()

    # Find the missing_column issue for 'Flag'
    missing_col_issues = [
        i
        for i in data["issues"]
        if i["type"] == "missing_column"
        and i.get("table") == "meta.languages"
        and i.get("column") == "Flag"
    ]

    assert len(missing_col_issues) == 1
    assert "not documented in catalog" in missing_col_issues[0]["message"]
