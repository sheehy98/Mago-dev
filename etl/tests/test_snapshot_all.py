#
# Imports
#

# Third party
import pytest

# Module under test
from dev.etl.snapshot_all import snapshot_all


#
# Fixtures
#

pytestmark = pytest.mark.usefixtures("restore_buckets", "redirect_all_paths")


#
# Tests for snapshot_all function
#


def test_snapshot_all_success():
    """
    Story: Snapshot all snapshots both tables and buckets

    Given the database and MinIO are running
    When we call snapshot_all
    Then it returns success
    """
    data = snapshot_all()

    assert data["status"] == "success"
    assert "tables" in data
    assert "bucket" in data


def test_snapshot_all_response_structure():
    """
    Story: Snapshot all returns proper response structure

    Given a valid request
    When we call snapshot_all
    Then it returns expected fields
    """
    data = snapshot_all()

    assert "status" in data
    assert "message" in data
    assert "tables" in data
    assert "bucket" in data
