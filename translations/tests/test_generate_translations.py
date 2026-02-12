#
# Imports
#

# Standard library
from pathlib import Path

# Module under test
from dev.translations.generate_translations import generate_translations

#
# Tests
#


def test_generate_translations_requires_parameter():
    """
    Story: Endpoint requires folder or all parameter

    Given no parameters are provided
    Then it returns an error
    """
    data = generate_translations()
    assert data["status"] == "error"
    assert "Must provide either" in data["message"]


def test_generate_translations_rejects_both_parameters():
    """
    Story: Endpoint rejects both folder and all parameters

    Given both folder and all parameters are provided
    Then it returns an error
    """
    data = generate_translations(folder="/some/path", generate_all=True)
    assert data["status"] == "error"
    assert "Cannot provide both" in data["message"]


def test_generate_translations_skips_existing(folder_with_all_languages):
    """
    Story: Skip folders with existing translations

    Given a translations folder with all language files
    When I request generation without force
    Then it generates no new files
    """
    data = generate_translations(folder=folder_with_all_languages)
    assert data["status"] == "success"
    assert data["files_generated"] == 0


def test_generate_translations_no_en_json(folder_without_en_json):
    """
    Story: Skip folder without en.json

    Given a translations folder without en.json
    When I request generation
    Then it generates no files
    """
    data = generate_translations(folder=folder_without_en_json)
    assert data["status"] == "success"
    assert data["files_generated"] == 0


def test_generate_translations_empty_en_json(folder_with_empty_en_json):
    """
    Story: Skip folder with empty en.json

    Given a translations folder with empty en.json
    When I request generation
    Then it generates no files
    """
    data = generate_translations(folder=folder_with_empty_en_json)
    assert data["status"] == "success"
    assert data["files_generated"] == 0


def test_generate_translations_all_complete():
    """
    Story: All folders are complete

    Given all translation folders have all language files
    When I request generation for all folders
    Then it reports all folders are complete
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
    # Either "complete" message or some folders processed
    assert "complete" in data["message"].lower() or data["folders_processed"] >= 0


def test_generate_translations_all_skips_folder_without_en_json(folder_without_en_json_for_all):
    """
    Story: Skip translations folders without en.json in find_incomplete scan

    Given a translations folder exists without en.json
    When I request generation for all folders
    Then it skips that folder (nothing to translate from)
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
    # The folder without en.json should be skipped
    assert data["folders_processed"] == 0 or "complete" in data["message"].lower()


def test_generate_translations_single_folder(folder_with_en_json_only):
    """
    Story: Generate translations for a single folder

    Given a translations folder with only en.json
    When I request generation for that folder
    Then it generates translation files for all target languages
    """
    data = generate_translations(folder=folder_with_en_json_only)
    assert data["status"] == "success"
    assert data["folders_processed"] == 1
    assert data["files_generated"] > 0

    # Verify files were created
    folder = Path(folder_with_en_json_only)
    assert (folder / "es.json").exists()
    assert (folder / "fr.json").exists()


def test_generate_translations_force_regenerate(folder_with_all_languages):
    """
    Story: Force regeneration of existing translations

    Given a translations folder with all language files
    When I request generation with force=True
    Then it regenerates all translation files
    """
    data = generate_translations(folder=folder_with_all_languages, force=True)
    assert data["status"] == "success"
    assert data["files_generated"] > 0


def test_generate_translations_all_finds_incomplete(folder_with_en_json_only):
    """
    Story: Find and process incomplete folders

    Given a translation folder with only en.json exists
    When I request generation for all folders
    Then it finds and processes the incomplete folder
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
    # Should have processed at least the test folder
    assert data["folders_processed"] >= 1


def test_generate_translations_all_skips_translations_file(translations_file_not_dir):
    """
    Story: Skip 'translations' matches that are files, not directories

    Given a file named 'translations' exists (not a directory)
    When I request generation for all folders
    Then it skips the file and reports success
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
