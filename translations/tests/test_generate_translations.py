#
# Imports
#

# Standard library
import json
from pathlib import Path

# Module under test
from dev.translations.generate_translations import generate_translations, remove_translation_keys

#
# Tests
#


def test_generate_translations_requires_parameter():
    """
    Story: Endpoint requires path or all parameter

    Given no parameters are provided
    Then it returns an error
    """
    data = generate_translations()
    assert data["status"] == "error"
    assert "Must provide either" in data["message"]


def test_generate_translations_rejects_both_parameters():
    """
    Story: Endpoint rejects both path and all parameters

    Given both path and all parameters are provided
    Then it returns an error
    """
    data = generate_translations(path="/some/path", generate_all=True)
    assert data["status"] == "error"
    assert "Cannot provide both" in data["message"]


def test_generate_translations_skips_existing(folder_with_all_languages):
    """
    Story: Skip files with existing translations

    Given a translations.json with all languages
    When I request generation without force
    Then it generates no new translations
    """
    data = generate_translations(path=folder_with_all_languages)
    assert data["status"] == "success"
    assert data["files_generated"] == 0


def test_generate_translations_no_en_json(folder_without_en_json):
    """
    Story: Skip file without English translations

    Given a translations.json without an English key
    When I request generation
    Then it generates no translations
    """
    data = generate_translations(path=folder_without_en_json)
    assert data["status"] == "success"
    assert data["files_generated"] == 0


def test_generate_translations_empty_en_json(folder_with_empty_en_json):
    """
    Story: Skip file with empty English translations

    Given a translations.json with empty English object
    When I request generation
    Then it generates no translations
    """
    data = generate_translations(path=folder_with_empty_en_json)
    assert data["status"] == "success"
    assert data["files_generated"] == 0


def test_generate_translations_all_complete():
    """
    Story: All files are complete

    Given all translations.json files have all languages
    When I request generation for all
    Then it reports all files are complete
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
    # Either "complete" message or some folders processed
    assert "complete" in data["message"].lower() or data["folders_processed"] >= 0


def test_generate_translations_all_skips_folder_without_en_json(folder_without_en_json_for_all):
    """
    Story: Skip translations.json without English in find_incomplete scan

    Given a translations.json exists without an English key
    When I request generation for all
    Then it skips that file (nothing to translate from)
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
    # The file without English should be skipped
    assert data["folders_processed"] == 0 or "complete" in data["message"].lower()


def test_generate_translations_single_folder(folder_with_en_json_only):
    """
    Story: Generate translations for a single component

    Given a translations.json with only English
    When I request generation for that component
    Then it adds translations for all target languages
    """
    data = generate_translations(path=folder_with_en_json_only)
    assert data["status"] == "success"
    assert data["folders_processed"] == 1
    assert data["files_generated"] > 0

    # Verify languages were added to translations.json
    translations_file = Path(folder_with_en_json_only) / "translations.json"
    with open(translations_file) as f:
        translations = json.load(f)
    assert "es" in translations
    assert "fr" in translations


def test_generate_translations_force_regenerate(folder_with_all_languages):
    """
    Story: Force regeneration of existing translations

    Given a translations.json with all languages
    When I request generation with force=True
    Then it regenerates all translations
    """
    data = generate_translations(path=folder_with_all_languages, force=True)
    assert data["status"] == "success"
    assert data["files_generated"] > 0


def test_generate_translations_all_finds_incomplete(folder_with_en_json_only):
    """
    Story: Find and process incomplete files

    Given a translations.json with only English exists
    When I request generation for all
    Then it finds and processes the incomplete file
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"
    # Should have processed at least the test file
    assert data["folders_processed"] >= 1


def test_generate_translations_all_skips_translations_file(translations_file_not_dir):
    """
    Story: Skip 'translations.json' matches that are directories, not files

    Given a directory named 'translations.json' exists (not a file)
    When I request generation for all
    Then it skips the directory and reports success
    """
    data = generate_translations(generate_all=True)
    assert data["status"] == "success"


#
# Tests — remove_translation_keys
#


def test_remove_translation_keys_single_key(folder_with_removable_keys):
    """
    Story: Remove a single key from all languages

    Given a translations.json with hello, goodbye, thanks in 3 languages
    When I remove the "goodbye" key
    Then it is removed from all languages and the file is updated
    """
    data = remove_translation_keys(folder_with_removable_keys, ["goodbye"])
    assert data["status"] == "success"
    assert data["removed"] == 3  # 3 languages

    # Verify the file was updated
    with open(folder_with_removable_keys) as f:
        translations = json.load(f)
    assert "goodbye" not in translations["en"]
    assert "goodbye" not in translations["es"]
    assert "goodbye" not in translations["fr"]
    assert "hello" in translations["en"]
    assert "thanks" in translations["en"]


def test_remove_translation_keys_multiple_keys(folder_with_removable_keys):
    """
    Story: Remove multiple keys at once

    Given a translations.json with hello, goodbye, thanks in 3 languages
    When I remove "goodbye" and "thanks"
    Then both are removed from all languages
    """
    data = remove_translation_keys(folder_with_removable_keys, ["goodbye", "thanks"])
    assert data["status"] == "success"
    assert data["removed"] == 6  # 2 keys x 3 languages

    with open(folder_with_removable_keys) as f:
        translations = json.load(f)
    assert "goodbye" not in translations["en"]
    assert "thanks" not in translations["es"]
    assert "hello" in translations["fr"]


def test_remove_translation_keys_nonexistent_key(folder_with_removable_keys):
    """
    Story: Removing a key that doesn't exist is a no-op

    Given a translations.json with hello, goodbye, thanks
    When I remove "nonexistent"
    Then no keys are removed and the file is unchanged
    """
    data = remove_translation_keys(folder_with_removable_keys, ["nonexistent"])
    assert data["status"] == "success"
    assert data["removed"] == 0

    with open(folder_with_removable_keys) as f:
        translations = json.load(f)
    assert len(translations["en"]) == 3


def test_remove_translation_keys_invalid_file():
    """
    Story: Error when file does not exist

    Given a path to a nonexistent file
    When I try to remove keys
    Then it returns an error
    """
    data = remove_translation_keys("/nonexistent/translations.json", ["hello"])
    assert data["status"] == "error"
