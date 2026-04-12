#
# Imports
#

# Standard library
import json

# Third party
import pytest

# Local
from dev.translations.tests.conftest import (
    get_test_issues,
    has_issue_type,
)

# Module under test
from dev.translations.validate_translations import validate_translations

#
# Tests
#


def test_validate_translations_returns_results():
    """
    Story: Validate translations endpoint works

    Given the API is running
    When I call the validate_translations endpoint
    Then I receive validation results
    """
    data = validate_translations()
    assert "status" in data
    assert "total_issues" in data
    assert "issues" in data


@pytest.mark.usefixtures("missing_language_files")
def test_missing_language_files():
    """
    Story: Validator detects missing languages

    Given a translations.json with only English
    Then it reports missing_language issues
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "missing_language")


@pytest.mark.usefixtures("key_mismatch")
def test_key_mismatch():
    """
    Story: Validator detects missing and extra keys

    Given en has [hello, goodbye] and es has [hello, extra]
    Then it reports missing_key for goodbye and extra_key for extra
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "missing_key")
    assert has_issue_type(issues, "extra_key")


@pytest.mark.usefixtures("invalid_json")
def test_invalid_json():
    """
    Story: Validator detects malformed JSON

    Given translations.json has invalid JSON syntax
    Then it reports json_parse_error
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "json_parse_error")


@pytest.mark.usefixtures("invalid_format")
def test_invalid_format():
    """
    Story: Validator detects non-dict language entry

    Given es entry is an array instead of object
    Then it reports invalid_format
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "invalid_format")


@pytest.mark.usefixtures("invalid_key_value")
def test_invalid_key_value():
    """
    Story: Validator detects empty keys and values

    Given translations have empty keys and empty values
    Then it reports invalid_key and invalid_value
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "invalid_key")
    assert has_issue_type(issues, "invalid_value")


@pytest.mark.usefixtures("component_uses_translations_no_folder")
def test_component_missing_translations_folder():
    """
    Story: Validator detects component using translations without file

    Given a component imports useTranslation
    And no translations.json exists
    Then it reports component_missing_translations
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "component_missing_translations")


@pytest.mark.usefixtures("component_with_hardcoded_text")
def test_component_hardcoded_text():
    """
    Story: Validator detects hardcoded text needing translations

    Given a component has hardcoded text like "Submit Form"
    And it doesn't use translations
    Then it reports component_needs_translations
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "component_needs_translations")


@pytest.mark.usefixtures("component_with_path_mismatch")
def test_component_path_mismatch():
    """
    Story: Validator detects useTranslation path mismatch

    Given useTranslation('wrong/path') but component is at _test_translations
    Then it reports translation_path_mismatch
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "translation_path_mismatch")


@pytest.mark.usefixtures("component_with_missing_key")
def test_component_missing_key():
    """
    Story: Validator detects missing translation keys in component

    Given component uses t('missing_key') but translations.json doesn't have it
    Then it reports component_missing_key
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "component_missing_key")


@pytest.mark.usefixtures("component_with_duplicate_use_translation")
def test_component_duplicate_use_translation():
    """
    Story: Validator detects duplicate useTranslation calls

    Given component calls useTranslation('same/path') twice
    Then it reports duplicate_use_translation
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "duplicate_use_translation")


@pytest.mark.usefixtures("component_with_aliased_t")
def test_component_aliased_translation_function():
    """
    Story: Validator detects aliased t function

    Given component uses { t: tTest } pattern
    Then it reports aliased_translation_function
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "aliased_translation_function")


@pytest.mark.usefixtures("orphaned_translation_folder")
def test_orphaned_translation_folder():
    """
    Story: Validator detects orphaned translation files

    Given translations.json exists with content
    And component doesn't use translations
    Then it reports orphaned_translation_folder
    """
    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "orphaned_translation_folder")


def test_component_with_hardcoded_text_uses_translations(test_base_dir):
    """
    Story: Validator detects hardcoded text in component that uses translations

    Given a component uses translations
    And it also has hardcoded text
    Then it reports component_hardcoded_text
    """
    test_base_dir.mkdir(parents=True, exist_ok=True)

    (test_base_dir / "translations.json").write_text(json.dumps({"en": {"hello": "Hello"}}))

    component = test_base_dir / "_test_translations.tsx"
    component.write_text("""
import { useTranslation } from '../providers/TranslationProvider';

export function TestComponent() {
    const { t } = useTranslation('_test_translations');
    return (
        <div>
            {t('hello')}
            <label>Hardcoded Text Here</label>
        </div>
    );
}
""")

    data = validate_translations()
    issues = get_test_issues(data)

    assert has_issue_type(issues, "component_hardcoded_text")


@pytest.mark.usefixtures("global_translations_extra_key")
def test_global_translations_extra_key():
    """
    Story: Validator detects extra keys in global translations

    Given translations.json has a key not found in any seed CSV
    Then it reports global_translations_extra_key
    """
    data = validate_translations()

    # Find the specific issue for our test key
    extra_key_issues = [
        i
        for i in data.get("issues", [])
        if i.get("type") == "global_translations_extra_key"
        and i.get("key") == "_test_extra_key_not_in_seed"
    ]

    assert len(extra_key_issues) == 1


def test_global_translations_missing_key(global_translations_missing_key):
    """
    Story: Validator detects missing keys in global translations

    Given a seed CSV has a Name value not in translations.json
    Then it reports global_translations_missing_key
    """
    # This fixture returns the removed key name
    missing_key = global_translations_missing_key

    data = validate_translations()

    # Find the specific issue for the removed key
    missing_key_issues = [
        i
        for i in data.get("issues", [])
        if i.get("type") == "global_translations_missing_key" and i.get("key") == missing_key
    ]

    assert len(missing_key_issues) == 1


@pytest.mark.usefixtures("global_translations_file_missing")
def test_global_translations_file_missing():
    """
    Story: Validator detects missing global translations.json file

    Given the global translations.json file does not exist
    Then it reports global_translations_missing
    """
    data = validate_translations()

    # Find the issue for missing global translations
    missing_file_issues = [
        i for i in data.get("issues", []) if i.get("type") == "global_translations_missing"
    ]

    assert len(missing_file_issues) == 1


@pytest.mark.usefixtures("seed_csv_file_missing")
def test_seed_csv_file_missing():
    """
    Story: Validator detects missing seed CSV file

    Given a seed CSV file does not exist
    Then it reports global_translations_seed_not_found
    """
    data = validate_translations()

    # Find the issue for missing seed file
    missing_seed_issues = [
        i for i in data.get("issues", []) if i.get("type") == "global_translations_seed_not_found"
    ]

    assert len(missing_seed_issues) == 1


@pytest.mark.usefixtures("global_translations_invalid_json")
def test_global_translations_invalid_json():
    """
    Story: Validator detects corrupted global translations.json file

    Given the global translations.json has invalid JSON
    Then it reports global_translations_missing with parse error
    """
    data = validate_translations()

    # Find the issue for corrupted global translations
    invalid_json_issues = [
        i
        for i in data.get("issues", [])
        if i.get("type") == "global_translations_missing"
        and "Failed to read" in i.get("message", "")
    ]

    assert len(invalid_json_issues) == 1


@pytest.mark.usefixtures("orphaned_translation_folder_no_component")
def test_orphaned_folder_no_component():
    """
    Story: Validator detects orphaned translations.json with no component

    Given a translations.json exists
    And there is no component file in the directory
    Then it reports orphaned_translation_folder with "no component found"
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should find the orphaned file
    orphaned_issues = [i for i in issues if i.get("type") == "orphaned_translation_folder"]
    assert len(orphaned_issues) == 1
    assert "no component found" in orphaned_issues[0].get("message", "")


@pytest.mark.usefixtures("component_with_filtered_text")
def test_filtered_text_not_flagged():
    """
    Story: Validator ignores text patterns that should be filtered

    Given a component has text that matches filter patterns:
    - Lowercase text (not starting with uppercase)
    - JSX expressions (containing curly braces)
    - Short text (less than 3 characters)
    - All caps text (LOADING, ERROR, etc.)
    - Variable-like placeholders ($var, @mention, callback())
    Then it does NOT report component_needs_translations
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should NOT flag this component since all text is filtered out
    assert not has_issue_type(issues, "component_needs_translations")


@pytest.mark.usefixtures("orphaned_translation_folder_nonstandard_name")
def test_orphaned_folder_nonstandard_component_name():
    """
    Story: Validator finds component via fallback glob search

    Given a translations.json exists in a subdirectory
    And the component file has a non-standard name (Main.tsx)
    Then the validator uses fallback glob search to find the component
    And it reports orphaned_translation_folder since component doesn't use translations
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should find the orphaned file using fallback glob search
    orphaned_issues = [i for i in issues if i.get("type") == "orphaned_translation_folder"]
    assert len(orphaned_issues) == 1
    # The message should indicate component found but not using translations
    assert "does not use" in orphaned_issues[0].get("message", "")
    # Verify component was found via fallback glob (not "no component found")
    assert "Main.tsx" in orphaned_issues[0].get("component", "")


@pytest.mark.usefixtures("orphaned_translation_folder_no_tsx_files")
def test_orphaned_folder_no_tsx_files():
    """
    Story: Validator handles translations.json with no component files

    Given a translations.json exists in a subdirectory
    And there are no .tsx or .ts files in the directory (only .css, .md, etc.)
    Then the validator reports orphaned_translation_folder with "no component found"
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should find the orphaned file
    orphaned_issues = [i for i in issues if i.get("type") == "orphaned_translation_folder"]
    assert len(orphaned_issues) == 1
    # Should say no component found since there are no .tsx/.ts files
    assert "no component found" in orphaned_issues[0].get("message", "")
    # Component should be None
    assert orphaned_issues[0].get("component") is None


@pytest.mark.usefixtures("empty_translation_folder")
def test_empty_translation_folder():
    """
    Story: Validator skips empty translations.json files

    Given a translations.json exists
    And it contains an empty JSON object
    Then the validator silently skips it (not an error)
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should NOT report any issues for the empty file
    assert len(issues) == 0


@pytest.mark.usefixtures("component_with_whitespace_button")
def test_whitespace_button_filtered():
    """
    Story: Validator filters buttons with whitespace-only content

    Given a component has buttons/links with only whitespace
    Then it does NOT report component_needs_translations
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should NOT flag this component since whitespace-only buttons are filtered
    assert not has_issue_type(issues, "component_needs_translations")


@pytest.mark.usefixtures("test_tsx_file")
def test_test_tsx_file_excluded():
    """
    Story: Validator excludes .test.tsx files from component discovery

    Given a .test.tsx file exists with hardcoded text
    Then it is NOT included in validation (excluded by pattern)
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should NOT flag anything - test files are excluded from discovery
    assert not has_issue_type(issues, "component_needs_translations")


@pytest.mark.usefixtures("translation_folder_missing_en_json")
def test_translation_folder_missing_en_json():
    """
    Story: Validator handles translations.json missing English

    Given a translations.json exists with es
    But en (the reference language) is missing
    Then it reports missing_language for en
    """
    data = validate_translations()
    issues = get_test_issues(data)

    # Should report en is missing
    missing_en = [
        i for i in issues if i.get("type") == "missing_language" and i.get("language") == "en"
    ]
    assert len(missing_en) == 1
