#
# Imports
#

# Standard library
import shutil

# Third party
import pytest

# Module under test
from dev.ollama.pull import pull_model

#
# Helpers
#


def ollama_installed() -> bool:
    """Check if ollama command is available"""
    return shutil.which("ollama") is not None


#
# Tests
#


def test_pull_model_empty_models():
    """
    Story: Endpoint requires non-empty models

    Given models is empty string
    Then it returns an error
    """
    data = pull_model(models="")
    assert "error" in data


def test_pull_model_whitespace_only():
    """
    Story: Endpoint requires actual model names

    Given models contains only whitespace/commas
    Then it returns an error
    """
    data = pull_model(models="  ,  ,  ")
    assert "error" in data
    assert "No valid models" in data["error"]


@pytest.mark.skipif(not ollama_installed(), reason="ollama not installed")
def test_pull_model_invalid_model():
    """
    Story: Handle invalid model names

    Given an invalid model name is provided
    Then it returns a failed status for that model
    """
    data = pull_model(models="nonexistent-model-xyz-12345")
    assert data["status"] == "partial"
    assert data["models_pulled"] == 0
    assert data["results"][0]["status"] == "failed"


@pytest.mark.skipif(not ollama_installed(), reason="ollama not installed")
def test_pull_model_success():
    """
    Story: Successfully pull a model

    Given a valid model name
    Then it pulls the model successfully
    """
    # Use a small model that's likely already pulled
    data = pull_model(models="llama3.2:3b")
    assert data["status"] == "success"
    assert data["models_pulled"] == 1
    assert data["results"][0]["status"] == "success"


@pytest.mark.skipif(not ollama_installed(), reason="ollama not installed")
def test_pull_model_response_structure():
    """
    Story: Response contains all expected fields

    Given any model pull attempt
    When I call pull_model
    Then the response contains status, message, models_pulled, total_models, and results
    """

    # Act
    data = pull_model(models="nonexistent-model-xyz-99999")

    # Assert
    assert "status" in data
    assert "message" in data
    assert "models_pulled" in data
    assert "total_models" in data
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 1
